"""MinIO 存储适配器集成测试（任务 16.3）。

在**不依赖真实 MinIO 服务器**的前提下，验证
:class:`~app.adapters.storage_service.MinioStorageService` 的关键契约：

* 需求 10.1 —— 保存成功返回系统内**唯一**的存储标识（``storage_id``）。
* 需求 10.2 —— 保存在 ``timeout_seconds`` 内未完成时终止并返回存储超时
  错误（:attr:`~app.core.errors.ErrorCode.STORAGE_TIMEOUT`）。

附带覆盖需求 10.3 的实现分支（其他存储错误 -> ``STORAGE_FAILED``），以确认
``save`` 的异常归类路径。

测试策略（如何 mock MinIO）：
    :class:`MinioStorageService` 的底层 ``minio.Minio`` 客户端经
    :meth:`MinioStorageService._get_client` **懒加载**，且 :meth:`_put`
    每次都通过 ``_get_client()`` 取用客户端。因此我们用 ``unittest.mock``
    将 ``_get_client`` 替换为返回 :class:`MagicMock` 客户端的桩：
      * ``bucket_exists`` 返回 ``True``（跳过建桶分支）；
      * ``put_object`` 按场景配置为「空操作 / 阻塞 / 抛异常」。
    由于 ``_get_client`` 是唯一创建真实客户端、产生网络连接的入口，替换它即可
    保证全程无任何真实网络 I/O。

超时用例的运行时说明：
    生产默认超时为 30 秒（``DEFAULT_TIMEOUT_SECONDS``）。为保持测试快速，
    本文件对超时用例显式传入很小的 ``timeout_seconds``（如 1 秒）。
    :meth:`MinioStorageService.save` 在 ``ThreadPoolExecutor`` 中执行阻塞
    上传并以 ``future.result(timeout=timeout_seconds)`` 施加超时，超时即返回
    :meth:`StorageResult.timeout`。小超时与默认 30s 走的是**同一段超时代码
    路径**，故小超时足以验证 30s 超时语义而无需真实等待 30 秒。
"""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from app.adapters.storage_service import MinioStorageService
from app.core.errors import ErrorCode


def _make_service() -> MinioStorageService:
    """构造一个带显式连接参数的服务实例（不触发任何连接）。"""
    return MinioStorageService(
        endpoint="localhost:9000",
        access_key="test-access",
        secret_key="test-secret",
        bucket="homework",
        secure=False,
    )


# --------------------------------------------------------------------------- #
# 需求 10.1：保存成功返回唯一 storage_id                                        #
# --------------------------------------------------------------------------- #


@pytest.mark.integration
def test_save_success_returns_unique_storage_id() -> None:
    """连续两次保存成功，均返回非空且互不相同的 ``storage_id``（需求 10.1）。

    用 mock 客户端替换真实 MinIO：``bucket_exists`` 返回 ``True``、
    ``put_object`` 为空操作。两次保存的 ``storage_id`` 必须 DISTINCT，
    以体现「系统内唯一存储标识」。
    """
    mock_client = MagicMock()
    mock_client.bucket_exists.return_value = True
    mock_client.put_object.return_value = None

    service = _make_service()
    with patch.object(service, "_get_client", return_value=mock_client):
        first = service.save("report.pdf", b"data-1")
        second = service.save("report.pdf", b"data-2")

    # 两次均成功且携带非空 storage_id。
    assert first.ok is True
    assert first.error_code is None
    assert first.storage_id
    assert second.ok is True
    assert second.error_code is None
    assert second.storage_id

    # 唯一性：即便对象名相同，两次返回的存储标识也必须不同。
    assert first.storage_id != second.storage_id

    # 确实尝试了写入对象存储（每次一次）。
    assert mock_client.put_object.call_count == 2
    # bucket_exists 为 True，故不应再创建桶。
    mock_client.make_bucket.assert_not_called()


@pytest.mark.integration
def test_save_creates_bucket_when_missing() -> None:
    """目标桶不存在时先建桶再写入，并仍返回成功标识（需求 10.1 的写入分支）。"""
    mock_client = MagicMock()
    mock_client.bucket_exists.return_value = False
    mock_client.put_object.return_value = None

    service = _make_service()
    with patch.object(service, "_get_client", return_value=mock_client):
        result = service.save("report.pdf", b"payload")

    assert result.ok is True
    assert result.storage_id
    mock_client.make_bucket.assert_called_once_with("homework")
    mock_client.put_object.assert_called_once()


# --------------------------------------------------------------------------- #
# 需求 10.2：超时返回 STORAGE_TIMEOUT                                           #
# --------------------------------------------------------------------------- #


@pytest.mark.integration
def test_save_timeout_returns_storage_timeout() -> None:
    """上传在 ``timeout_seconds`` 内未完成 -> 返回 STORAGE_TIMEOUT（需求 10.2）。

    将 ``put_object`` 配置为阻塞（超过给定的小超时），并以 ``timeout_seconds=1``
    调用 :meth:`save`，使 ``future.result(timeout=1)`` 触发超时分支。生产默认
    30s 走的是同一段超时代码，故用小超时即可验证语义并保持测试快速。
    """
    # 工作线程在此事件上等待；以略大于超时的上限作为安全兜底，避免线程滞留。
    release = threading.Event()

    def blocking_put_object(*_args: object, **_kwargs: object) -> None:
        # 阻塞约 2 秒（> 1 秒超时），确保 future 在超时点仍未完成。
        release.wait(timeout=2.0)

    mock_client = MagicMock()
    mock_client.bucket_exists.return_value = True
    mock_client.put_object.side_effect = blocking_put_object

    service = _make_service()
    try:
        with patch.object(service, "_get_client", return_value=mock_client):
            start = time.monotonic()
            result = service.save("report.pdf", b"data", timeout_seconds=1)
            elapsed = time.monotonic() - start
    finally:
        # 释放工作线程，避免后续测试受阻塞线程影响。
        release.set()

    assert result.ok is False
    assert result.error_code == ErrorCode.STORAGE_TIMEOUT
    assert result.storage_id is None
    # 确实尝试了上传（进入了阻塞调用）。
    mock_client.put_object.assert_called_once()
    # 远快于生产默认的 30s，证明超时是按传入的小超时生效。
    assert elapsed < 30.0


# --------------------------------------------------------------------------- #
# 需求 10.3：其他存储错误 -> STORAGE_FAILED（实现分支佐证）                      #
# --------------------------------------------------------------------------- #


@pytest.mark.integration
def test_save_error_returns_storage_failed_on_put_object_exception() -> None:
    """``put_object`` 抛异常 -> 返回 STORAGE_FAILED（需求 10.3 分支）。"""
    mock_client = MagicMock()
    mock_client.bucket_exists.return_value = True
    mock_client.put_object.side_effect = RuntimeError("connection reset")

    service = _make_service()
    with patch.object(service, "_get_client", return_value=mock_client):
        result = service.save("report.pdf", b"data")

    assert result.ok is False
    assert result.error_code == ErrorCode.STORAGE_FAILED
    assert result.storage_id is None


@pytest.mark.integration
def test_save_error_returns_storage_failed_on_bucket_exists_exception() -> None:
    """``bucket_exists`` 抛异常（连接失败）-> 返回 STORAGE_FAILED（需求 10.3 分支）。"""
    mock_client = MagicMock()
    mock_client.bucket_exists.side_effect = OSError("cannot connect to MinIO")

    service = _make_service()
    with patch.object(service, "_get_client", return_value=mock_client):
        result = service.save("report.pdf", b"data")

    assert result.ok is False
    assert result.error_code == ErrorCode.STORAGE_FAILED
    assert result.storage_id is None
    mock_client.put_object.assert_not_called()
