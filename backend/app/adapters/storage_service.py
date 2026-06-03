"""文件存储服务适配器（MinIO）。

依据 design.md「Storage_Service（MinIO 适配器接口）」与「Error Handling
（存储失败无重试）」定义，本模块提供对象存储的统一抽象：

* :class:`StorageResult` —— 保存操作的结果类型（成功携带唯一 ``storage_id``，
  失败携带 :class:`~app.core.errors.ErrorCode`）。
* :class:`StorageService` —— 存储服务协议（``Protocol``），约定 :meth:`save`
  的语义：成功返回唯一 ``storage_id``；30 秒内未完成返回存储超时；其他错误
  返回存储失败。``Submission_Service`` 对该调用执行 0 次重试（本适配器仅做
  一次尝试）。
* :class:`MinioStorageService` —— 基于 minio Python SDK 的生产实现，懒连接
  （导入与构造时不连接 MinIO），并对阻塞调用施加超时控制。
* :class:`FakeStorageService` —— 内存实现，供服务层属性/单元测试注入；可通过
  开关模拟成功/失败/超时，且每次成功保存返回互不相同的 ``storage_id``
  （需求 10.4 唯一性）。

需求追溯：
* 10.1 —— 保存成功返回系统内唯一存储标识。
* 10.2 —— 30 秒内未完成保存则返回存储超时错误。
* 10.4 —— 每个存储标识唯一（互不重复）。
"""

from __future__ import annotations

import io
import os
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from typing import Dict, Optional, Protocol, runtime_checkable

import logging

from app.core.errors import ErrorCode

__all__ = [
    "StorageResult",
    "StorageService",
    "MinioStorageService",
    "FakeStorageService",
]

logger = logging.getLogger(__name__)

# 默认保存超时（秒），与设计/需求 10.2 一致。
DEFAULT_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class StorageResult:
    """不可变的存储保存结果。

    Attributes:
        ok: 保存是否成功。
        storage_id: 成功时为系统内唯一的对象存储标识；失败时为 ``None``。
        error_code: 失败时为对应错误码（:attr:`ErrorCode.STORAGE_TIMEOUT`
            或 :attr:`ErrorCode.STORAGE_FAILED`）；成功时为 ``None``。
    """

    ok: bool
    storage_id: Optional[str] = None
    error_code: Optional[ErrorCode] = None

    def __post_init__(self) -> None:
        # 保持结果自洽：成功必须携带 storage_id 且无错误码；失败相反。
        if self.ok:
            if not self.storage_id:
                raise ValueError("成功的 StorageResult 必须携带 storage_id")
            if self.error_code is not None:
                raise ValueError("成功的 StorageResult 不应携带 error_code")
        else:
            if self.error_code is None:
                raise ValueError("失败的 StorageResult 必须携带 error_code")
            if self.storage_id is not None:
                raise ValueError("失败的 StorageResult 不应携带 storage_id")

    @classmethod
    def success(cls, storage_id: str) -> "StorageResult":
        """构造一个表示保存成功的结果。"""
        return cls(ok=True, storage_id=storage_id, error_code=None)

    @classmethod
    def timeout(cls) -> "StorageResult":
        """构造一个表示存储超时的结果（需求 10.2）。"""
        return cls(ok=False, storage_id=None, error_code=ErrorCode.STORAGE_TIMEOUT)

    @classmethod
    def failed(cls) -> "StorageResult":
        """构造一个表示存储失败的结果（需求 10.3）。"""
        return cls(ok=False, storage_id=None, error_code=ErrorCode.STORAGE_FAILED)


@runtime_checkable
class StorageService(Protocol):
    """存储服务协议。

    实现需保证：保存成功返回系统内唯一 ``storage_id``；在
    ``timeout_seconds`` 内未完成返回 :attr:`ErrorCode.STORAGE_TIMEOUT`；
    其他任何错误返回 :attr:`ErrorCode.STORAGE_FAILED`。本协议仅描述单次
    尝试语义；重试策略由调用方（``Submission_Service`` 执行 0 次重试）决定。
    """

    def save(
        self,
        object_name: str,
        data: bytes,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        prefix: Optional[str] = None,
    ) -> StorageResult:
        """保存对象并返回结果。

        Args:
            object_name: 原始文件名/对象名，用于派生最终对象键与 ``storage_id``。
            data: 待保存的字节内容。
            timeout_seconds: 保存超时上限（秒），默认 30。
            prefix: 可选的分层路径前缀（如 ``"课程/作业/学号_姓名"``），用于在对象
                存储中按层级组织文件，避免全部堆在桶根目录。

        Returns:
            :class:`StorageResult`：成功携带唯一 ``storage_id``；超时或错误
            携带相应 :class:`ErrorCode`。
        """
        ...


def _sanitize_segment(segment: str) -> str:
    """清洗单个路径段：去除路径分隔符与首尾空白，禁止 ``.`` / ``..`` 等危险值。

    用于将课程名/作业标题/学生标识等转换为安全的对象键路径段（保留中文等 UTF-8
    字符，MinIO 与本地磁盘均可正确处理）。空或非法段回退为 ``"_"``。
    """
    text = (segment or "").strip().replace("/", "_").replace("\\", "_")
    # 去除控制字符与对部分文件系统不友好的字符。
    for bad in ('\0', ':', '*', '?', '"', '<', '>', '|', '\n', '\r', '\t'):
        text = text.replace(bad, "_")
    text = text.strip(". ")
    return text or "_"


def _generate_object_key(object_name: str, prefix: Optional[str] = None) -> str:
    """基于 uuid4 与原始文件名派生系统内唯一的对象键 / storage_id。

    形如 ``"<uuid4hex>-<safe_name>"``，uuid4 保证唯一性，保留原始名便于排查。
    若提供 ``prefix``（可含 ``/`` 分隔的多级路径），则将其各段清洗后作为前缀，
    生成形如 ``"课程/作业/学号_姓名/<uuid4hex>-<safe_name>"`` 的分层对象键，使文件
    在对象存储中按课程→作业→学生组织，而非全部堆在桶根目录。
    """

    safe_name = (object_name or "file").strip().replace("/", "_").replace("\\", "_")
    key = f"{uuid.uuid4().hex}-{safe_name}"
    if prefix:
        segments = [_sanitize_segment(s) for s in str(prefix).split("/") if s.strip()]
        if segments:
            key = "/".join(segments) + "/" + key
    return key


def _parse_endpoint(raw: str) -> tuple[str, Optional[bool]]:
    """解析 MinIO 端点：剥离 ``http(s)://`` 前缀并推断是否启用 TLS。

    minio SDK 的 :class:`~minio.Minio` 要求 ``endpoint`` 为不含协议的 ``host[:port]``，
    并以独立的 ``secure`` 布尔开关控制 TLS。本函数兼容直接配置形如
    ``https://apioss.minglog.cn`` 的完整 URL：

    * ``https://host`` -> ``("host", True)``
    * ``http://host``  -> ``("host", False)``
    * ``host:9000``    -> ``("host:9000", None)``（由调用方按 ``MINIO_SECURE`` 决定）

    返回 ``(endpoint, secure_or_none)``；``secure`` 为 ``None`` 表示 URL 未携带协议、
    无法推断，应回退到显式配置。尾部斜杠与路径会被去除（SDK 只接受 host[:port]）。
    """
    value = (raw or "").strip()
    secure: Optional[bool] = None
    if value.lower().startswith("https://"):
        value = value[len("https://"):]
        secure = True
    elif value.lower().startswith("http://"):
        value = value[len("http://"):]
        secure = False
    # 去除路径/查询部分，仅保留 host[:port]。
    value = value.split("/", 1)[0].strip("/")
    return value, secure


class MinioStorageService:
    """基于 minio Python SDK 的存储服务实现。

    构造时**不**建立网络连接；底层 :class:`minio.Minio` 客户端在首次
    :meth:`save` 调用时懒加载，因此模块导入与对象构造不要求 MinIO 在线。
    连接参数可经构造函数或环境变量配置，并提供本地开发默认值。

    环境变量（构造函数参数优先）：
        * ``MINIO_ENDPOINT``（默认 ``"localhost:9000"``）——可带 ``http(s)://``
          前缀，带前缀时自动推断 ``secure`` 并剥离协议。
        * ``MINIO_ACCESS_KEY``（默认 ``"minioadmin"``）
        * ``MINIO_SECRET_KEY``（默认 ``"minioadmin"``）
        * ``MINIO_BUCKET``（默认 ``"homework"``）
        * ``MINIO_REGION``（默认 ``None``，部分部署需要显式区域，如 ``us-east-1``）
        * ``MINIO_SECURE``（默认 ``"false"``，取值 ``true/1/yes`` 视为启用 TLS）。
          当 ``MINIO_ENDPOINT`` 自带 ``http(s)://`` 协议时，由协议推断 TLS，
          ``MINIO_SECURE`` 不再生效。
    """

    def __init__(
        self,
        endpoint: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        bucket: Optional[str] = None,
        secure: Optional[bool] = None,
        region: Optional[str] = None,
    ) -> None:
        raw_endpoint = endpoint or os.getenv("MINIO_ENDPOINT", "localhost:9000")
        parsed_endpoint, inferred_secure = _parse_endpoint(raw_endpoint)
        self.endpoint = parsed_endpoint
        self.access_key = access_key or os.getenv("MINIO_ACCESS_KEY", "minioadmin")
        self.secret_key = secret_key or os.getenv("MINIO_SECRET_KEY", "minioadmin")
        self.bucket = bucket or os.getenv("MINIO_BUCKET", "homework")
        self.region = region or os.getenv("MINIO_REGION") or None
        if secure is not None:
            # 显式参数优先。
            self.secure = secure
        elif inferred_secure is not None:
            # 端点 URL 自带协议时由协议推断。
            self.secure = inferred_secure
        else:
            self.secure = os.getenv("MINIO_SECURE", "false").strip().lower() in {
                "true",
                "1",
                "yes",
            }
        # 懒加载的客户端句柄；首次保存时初始化。
        self._client = None

    def _get_client(self):
        """懒加载并返回 minio 客户端（首次调用时导入并连接配置）。"""
        if self._client is None:
            # 延迟导入：避免模块导入阶段对 minio SDK 产生硬依赖/副作用。
            from minio import Minio

            self._client = Minio(
                self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure,
                region=self.region,
            )
        return self._client

    def _put(self, object_key: str, data: bytes) -> None:
        """执行一次阻塞式上传（必要时创建桶）。"""
        client = self._get_client()
        # 确保目标桶存在；若不存在则创建。
        if not client.bucket_exists(self.bucket):
            client.make_bucket(self.bucket)
        client.put_object(
            self.bucket,
            object_key,
            io.BytesIO(data),
            length=len(data),
        )

    def save(
        self,
        object_name: str,
        data: bytes,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        prefix: Optional[str] = None,
    ) -> StorageResult:
        """将对象写入 MinIO，超时或错误返回相应结果（需求 10.1/10.2）。

        在独立线程中执行阻塞上传，并对其施加 ``timeout_seconds`` 超时；
        超时返回 :attr:`ErrorCode.STORAGE_TIMEOUT`，其他异常返回
        :attr:`ErrorCode.STORAGE_FAILED`。本方法仅尝试一次（0 重试）。
        ``prefix`` 用于派生分层对象键（课程/作业/学生）。
        """
        object_key = _generate_object_key(object_name, prefix)
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self._put, object_key, data)
                try:
                    future.result(timeout=timeout_seconds)
                except FuturesTimeoutError:
                    # 取消（尽力而为）并返回超时错误。
                    future.cancel()
                    logger.warning(
                        "MinIO 保存超时：endpoint=%s bucket=%s object=%s timeout=%ss",
                        self.endpoint,
                        self.bucket,
                        object_key,
                        timeout_seconds,
                    )
                    return StorageResult.timeout()
        except Exception as exc:
            # 捕获连接、权限、IO 等所有其他错误，统一归为存储失败。
            # 记录具体异常原因，便于排查（如 DNS 解析失败、凭据错误、桶不存在等）。
            logger.error(
                "MinIO 保存失败：endpoint=%s secure=%s bucket=%s object=%s reason=%s: %s",
                self.endpoint,
                self.secure,
                self.bucket,
                object_key,
                type(exc).__name__,
                exc,
            )
            return StorageResult.failed()
        return StorageResult.success(object_key)

    def load(self, storage_id: str) -> Optional[bytes]:
        """读取 ``storage_id`` 对应对象的字节内容；不存在或出错返回 ``None``。"""
        try:
            client = self._get_client()
            response = client.get_object(self.bucket, storage_id)
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()
        except Exception:
            return None

    def delete(self, storage_id: str) -> None:
        """删除 ``storage_id`` 对应的对象（不存在或出错则忽略）。"""
        try:
            client = self._get_client()
            client.remove_object(self.bucket, storage_id)
        except Exception:
            pass


class FakeStorageService:
    """内存存储服务实现，供测试注入。

    将字节内容保存在以 ``storage_id`` 为键的字典中；每次成功保存返回互不
    相同的 ``storage_id``（满足需求 10.4 唯一性）。可通过开关模拟失败与超时，
    以便下游提交服务测试（13.x）验证存储失败/超时分支。

    Args:
        fail: 为 ``True`` 时所有 :meth:`save` 返回 :attr:`ErrorCode.STORAGE_FAILED`。
        timeout: 为 ``True`` 时所有 :meth:`save` 返回 :attr:`ErrorCode.STORAGE_TIMEOUT`。
            ``timeout`` 优先于 ``fail``。

    Attributes:
        objects: ``storage_id -> bytes`` 的已保存内容映射。
        save_call_count: :meth:`save` 被调用的累计次数（便于断言 0 重试）。
    """

    def __init__(self, fail: bool = False, timeout: bool = False) -> None:
        self.fail = fail
        self.timeout = timeout
        self.objects: Dict[str, bytes] = {}
        self.save_call_count = 0

    def set_mode(self, *, fail: bool = False, timeout: bool = False) -> None:
        """运行时调整模拟模式（成功/失败/超时）。"""
        self.fail = fail
        self.timeout = timeout

    def save(
        self,
        object_name: str,
        data: bytes,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        prefix: Optional[str] = None,
    ) -> StorageResult:
        """按当前模式返回结果；成功时保存内容并返回唯一 ``storage_id``。"""
        self.save_call_count += 1
        if self.timeout:
            return StorageResult.timeout()
        if self.fail:
            return StorageResult.failed()
        storage_id = _generate_object_key(object_name, prefix)
        # uuid4 理论上不会碰撞；防御性地确保键唯一。
        while storage_id in self.objects:
            storage_id = _generate_object_key(object_name, prefix)
        self.objects[storage_id] = data
        return StorageResult.success(storage_id)

    def load(self, storage_id: str) -> Optional[bytes]:
        """读取已保存内容；不存在返回 ``None``。"""
        return self.objects.get(storage_id)

    def delete(self, storage_id: str) -> None:
        """删除已保存内容（不存在则忽略）。"""
        self.objects.pop(storage_id, None)


# --------------------------------------------------------------------------- #
# 本地磁盘存储实现                                                              #
# --------------------------------------------------------------------------- #


class LocalDiskStorageService:
    """将上传文件保存到本地磁盘的存储服务实现。

    相比 MinIO，本实现零外部依赖、开箱即用，适合本地开发与课程演示。每个对象以
    唯一 ``storage_id``（``<uuid4hex>-<safe_name>``）作为文件名保存在 ``base_dir``
    目录下；``storage_id`` 与磁盘文件一一对应（需求 10.4 唯一性）。

    Args:
        base_dir: 文件保存根目录；为 ``None`` 时取环境变量 ``STORAGE_DIR``，
            缺省为项目内 ``uploaded_files`` 目录。目录不存在时自动创建。
    """

    def __init__(self, base_dir: Optional[str] = None) -> None:
        resolved = base_dir or os.getenv("STORAGE_DIR") or os.path.join(os.getcwd(), "uploaded_files")
        self.base_dir = os.path.abspath(resolved)
        os.makedirs(self.base_dir, exist_ok=True)

    def path_for(self, storage_id: str) -> str:
        """返回 ``storage_id`` 对应的磁盘绝对路径（不校验存在性）。

        支持以 ``/`` 分隔的多级 ``storage_id``（分层存储）。对每一段做清洗并禁止
        ``..`` 等路径穿越，最终路径必须落在 ``base_dir`` 之内。
        """
        # 逐段清洗，去除空段与穿越段，保证结果不会逃出 base_dir。
        raw_segments = str(storage_id).replace("\\", "/").split("/")
        safe_segments = []
        for seg in raw_segments:
            seg = seg.strip()
            if not seg or seg in (".", ".."):
                continue
            safe_segments.append(os.path.basename(seg))
        if not safe_segments:
            safe_segments = ["file"]
        candidate = os.path.abspath(os.path.join(self.base_dir, *safe_segments))
        # 双重保险：确保结果在 base_dir 之内。
        if os.path.commonpath([candidate, self.base_dir]) != self.base_dir:
            candidate = os.path.join(self.base_dir, safe_segments[-1])
        return candidate

    def save(
        self,
        object_name: str,
        data: bytes,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        prefix: Optional[str] = None,
    ) -> StorageResult:
        """将字节内容写入磁盘，成功返回唯一 ``storage_id``（支持分层 ``prefix``）。"""
        storage_id = _generate_object_key(object_name, prefix)
        path = self.path_for(storage_id)
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as fh:
                fh.write(data)
        except Exception:
            return StorageResult.failed()
        return StorageResult.success(storage_id)

    def load(self, storage_id: str) -> Optional[bytes]:
        """读取 ``storage_id`` 对应文件的字节内容；不存在返回 ``None``。"""
        path = self.path_for(storage_id)
        if not os.path.isfile(path):
            return None
        try:
            with open(path, "rb") as fh:
                return fh.read()
        except Exception:
            return None

    def delete(self, storage_id: str) -> None:
        """删除 ``storage_id`` 对应的磁盘文件（不存在则忽略）。"""
        path = self.path_for(storage_id)
        try:
            if os.path.isfile(path):
                os.remove(path)
        except Exception:
            pass


__all__.append("LocalDiskStorageService")
