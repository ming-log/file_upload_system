"""邮件服务（Email_Service，SMTP 适配器）。

依据 design.md「Components and Interfaces / Email_Service（SMTP 适配器接口）」与
需求 11 实现。本模块当前（任务 15.1）只实现 **两个纯函数**，二者无副作用、给定
相同输入恒得相同输出，便于属性测试（Hypothesis）直接断言：

1. :func:`build_email_body` —— 构造提交成功通知邮件的正文，包含作业标题、精确到
   秒（``YYYY-MM-DD HH:MM:SS``）的提交时间与提交文件名（需求 11.2，对应
   design「Correctness Properties」Property 33）。
2. :func:`next_attempt_schedule` —— 计算发送失败后的重试调度（每次重试相对首次
   失败的延迟秒数列表），用于驱动 :meth:`EmailService.notify_submission` 的重试逻辑
   （需求 11.5，对应 Property 35）。

异步发送/跳过/重试编排（:meth:`EmailService.notify_submission`，**任务 15.4**）：
* 邮箱为空（``None`` 或仅空白）→ 跳过发送并记录一条含 ``submission_id`` 与原因
  “邮箱缺失”的日志（需求 11.3 / Property 34），不发起任何 I/O。
* 邮箱非空 → 立即发起发送；单次发送施加 30 秒超时，超时即判失败（需求 11.4）；
  失败后按 :func:`next_attempt_schedule` 以 10 秒间隔最多重试 2 次（累计 ≤ 3 次，
  需求 11.5）；全部失败 → 记录含 ``submission_id`` 与失败原因的失败日志，且**绝不**
  向调用方抛出异常（保持已创建的提交记录有效，不回滚，需求 11.6 / Property 36）。

可测试性设计（供任务 15.5 / 15.6 注入 fake 而无需真实 SMTP / 真实等待）：
:class:`EmailService` 通过构造函数注入全部副作用依赖，且均提供生产默认值：

* ``sender``：异步“单次发送”可调用对象 ``async (recipient, body) -> None``；默认实现
  基于 aiosmtplib（懒导入、构造/导入期不连接）。测试注入成功/失败/抛 ``TimeoutError``
  的 fake 以确定性地驱动重试逻辑。
* ``sleep``：异步休眠函数（默认 :func:`asyncio.sleep`）。测试注入 no-op 以避免真实 10 秒等待。
* ``logger``：标准库 :class:`logging.Logger`（默认 ``logging.getLogger(__name__)``）。
  日志消息以 ``submission_id=<id>`` / ``reason=<原因>`` 形式可解析，便于测试断言。
* ``timeout_seconds``：单次发送超时（默认 30 秒，需求 11.4），经 :func:`asyncio.wait_for`
  施加；测试可设极小值，或令 fake sender 直接抛 :class:`asyncio.TimeoutError` 模拟超时。
* ``max_retries`` / ``retry_interval_seconds``：重试调度参数（默认 2 次 / 10 秒，需求 11.5）。

纯函数同时以 **模块级函数** 暴露（供属性测试直接导入调用），并在
:class:`EmailService` 上提供同名方法 :meth:`EmailService.build_email_body`
（与 design 接口签名一致）委托至模块级实现。
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Awaitable, Callable, Optional

__all__ = [
    "EMAIL_TIME_FORMAT",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_RETRY_INTERVAL_SECONDS",
    "DEFAULT_SEND_TIMEOUT_SECONDS",
    "DEFAULT_EMAIL_SUBJECT",
    "EMAIL_MISSING_REASON",
    "SendFn",
    "SubmissionRecord",
    "build_email_body",
    "next_attempt_schedule",
    "EmailService",
]

#: 模块级日志记录器（默认注入到 :class:`EmailService`，可被构造函数覆盖）。
logger = logging.getLogger(__name__)

#: “单次发送”可调用对象类型：``async (recipient, body) -> None``，成功返回、失败抛异常。
SendFn = Callable[[str, str], Awaitable[None]]


# --------------------------------------------------------------------------- #
# 常量定义                                                                      #
# --------------------------------------------------------------------------- #

#: 邮件正文中提交时间的格式：精确到年月日时分秒（需求 11.2 / Property 33）。
#: 例如 ``2024-05-01 09:30:05``。
EMAIL_TIME_FORMAT: str = "%Y-%m-%d %H:%M:%S"

#: 发送失败后的默认最大重试次数（需求 11.5：累计发送尝试 ≤ 3，即最多重试 2 次）。
DEFAULT_MAX_RETRIES: int = 2

#: 默认重试间隔（秒）。来源：需求 11.5（以 10 秒间隔重试）。
DEFAULT_RETRY_INTERVAL_SECONDS: int = 10

#: 单次发送尝试的默认超时（秒）。来源：需求 11.4（30 秒内未收到成功响应判失败）。
DEFAULT_SEND_TIMEOUT_SECONDS: int = 30

#: 通知邮件默认主题。
DEFAULT_EMAIL_SUBJECT: str = "作业提交成功通知"

#: 空邮箱跳过发送时记入日志的原因（需求 11.3 / Property 34）。
EMAIL_MISSING_REASON: str = "邮箱缺失"


# --------------------------------------------------------------------------- #
# 数据类型                                                                      #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SubmissionRecord:
    """通知邮件所需的提交记录视图（不可变）。

    仅承载发送通知所需的最小字段集合，便于在不依赖 ORM 会话的情况下构造与断言
    （任务 15.4/15.5/15.6 将据此实现异步发送与日志）。

    Attributes:
        submission_id: 提交记录标识，用于日志中定位记录（需求 11.3 / 11.6）。
        assignment_title: 关联作业标题，写入邮件正文（需求 11.2）。
        submitted_at: 提交时间，写入邮件正文（精确到秒，需求 11.2）。
        file_name: 提交文件名，写入邮件正文（需求 11.2）。
    """

    submission_id: str
    assignment_title: str
    submitted_at: datetime
    file_name: str


# --------------------------------------------------------------------------- #
# 纯函数                                                                        #
# --------------------------------------------------------------------------- #


def build_email_body(
    assignment_title: str, submitted_at: datetime, file_name: str
) -> str:
    """构造提交成功通知邮件的正文（纯函数）。

    正文必定包含以下三项信息（需求 11.2，对应 Property 33）：

    * 作业标题 ``assignment_title``；
    * 提交时间，按 :data:`EMAIL_TIME_FORMAT`（``YYYY-MM-DD HH:MM:SS``）格式化到秒；
    * 提交文件名 ``file_name``。

    确切格式（多行纯文本，字段以 ``：`` 分隔，便于断言与人工阅读）::

        作业提交成功通知

        您好，您的作业已成功提交，详情如下：

        作业标题：{assignment_title}
        提交时间：{submitted_at:YYYY-MM-DD HH:MM:SS}
        提交文件：{file_name}

        如非本人操作，请及时联系老师。

    Args:
        assignment_title: 作业标题，原样写入正文。
        submitted_at: 提交时间；以 :data:`EMAIL_TIME_FORMAT` 格式化（秒精度）。
        file_name: 提交文件名，原样写入正文。

    Returns:
        组装好的邮件正文字符串。
    """
    formatted_time = submitted_at.strftime(EMAIL_TIME_FORMAT)
    return (
        "作业提交成功通知\n"
        "\n"
        "您好，您的作业已成功提交，详情如下：\n"
        "\n"
        f"作业标题：{assignment_title}\n"
        f"提交时间：{formatted_time}\n"
        f"提交文件：{file_name}\n"
        "\n"
        "如非本人操作，请及时联系老师。"
    )


def next_attempt_schedule(
    max_retries: int = DEFAULT_MAX_RETRIES,
    interval_seconds: int = DEFAULT_RETRY_INTERVAL_SECONDS,
) -> list[int]:
    """返回每次重试相对首次失败的延迟秒数列表（纯函数）。

    语义（需求 11.5，对应 Property 35）：

    * 列表长度等于 ``max_retries``（默认 2），即重试次数；
    * 每个元素等于 ``interval_seconds``（默认 10），即两次发送尝试之间的固定间隔秒数；
    * 因此累计发送尝试次数 = ``max_retries + 1``（首次发送 + 各次重试），默认 ≤ 3。

    例如默认参数返回 ``[10, 10]``：表示首次发送失败后等待 10 秒重试一次、若再失败
    再等待 10 秒重试一次，共计 3 次发送尝试。

    ``max_retries <= 0`` 时返回空列表 ``[]``（不重试，仅首次发送）。

    Args:
        max_retries: 最大重试次数（首次发送之外的额外尝试次数）。
        interval_seconds: 相邻两次发送尝试之间的固定延迟（秒）。

    Returns:
        长度为 ``max(max_retries, 0)`` 的列表，每项均为 ``interval_seconds``。
    """
    if max_retries <= 0:
        return []
    return [interval_seconds] * max_retries


# --------------------------------------------------------------------------- #
# 服务类                                                                        #
# --------------------------------------------------------------------------- #


class EmailService:
    """SMTP 邮件服务适配器。

    提供与 design 接口一致的两个能力：

    * :meth:`build_email_body` —— 纯函数（委托模块级实现），构造邮件正文。
    * :meth:`notify_submission` —— 异步发送编排：空邮箱跳过并记日志；非空则发起
      发送、单次 30s 超时判失败、按调度以 10s 间隔最多重试 2 次；全部失败记日志
      且不抛出（不回滚提交，需求 11.6）。

    所有副作用依赖经构造函数注入并提供生产默认值，便于测试以 fake 替换（无需真实
    SMTP / 真实等待）：

    Args:
        sender: 异步“单次发送”可调用对象 ``async (recipient, body) -> None``。
            成功返回、失败抛异常（含 :class:`asyncio.TimeoutError`）。默认使用基于
            aiosmtplib 的 :meth:`_smtp_send`（懒导入、构造期不连接）。
        sleep: 异步休眠函数（``async (seconds) -> None``）。默认 :func:`asyncio.sleep`；
            测试可注入 no-op 以避免真实等待。
        logger: 日志记录器，默认模块级 :data:`logger`（``logging.getLogger(__name__)``）。
        timeout_seconds: 单次发送超时（秒），默认 :data:`DEFAULT_SEND_TIMEOUT_SECONDS`（30）。
        max_retries: 失败后最大重试次数，默认 :data:`DEFAULT_MAX_RETRIES`（2）。
        retry_interval_seconds: 相邻两次发送尝试的间隔（秒），默认
            :data:`DEFAULT_RETRY_INTERVAL_SECONDS`（10）。
        subject: 邮件主题，默认 :data:`DEFAULT_EMAIL_SUBJECT`。
        smtp_host / smtp_port / smtp_username / smtp_password / smtp_use_tls / sender_address:
            默认 aiosmtplib 发送实现的连接参数；为 ``None`` 时回退到对应环境变量与
            本地开发默认值（连接发生在 :meth:`notify_submission` 调用时，而非导入/构造期）。
    """

    def __init__(
        self,
        sender: Optional[SendFn] = None,
        *,
        sleep: Optional[Callable[[float], Awaitable[None]]] = None,
        logger: Optional[logging.Logger] = None,
        timeout_seconds: int = DEFAULT_SEND_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_interval_seconds: int = DEFAULT_RETRY_INTERVAL_SECONDS,
        subject: str = DEFAULT_EMAIL_SUBJECT,
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None,
        smtp_username: Optional[str] = None,
        smtp_password: Optional[str] = None,
        smtp_use_tls: Optional[bool] = None,
        sender_address: Optional[str] = None,
    ) -> None:
        # 注入点：未显式提供时回退到基于 aiosmtplib 的默认发送实现。
        self._sender: SendFn = sender if sender is not None else self._smtp_send
        self._sleep: Callable[[float], Awaitable[None]] = (
            sleep if sleep is not None else asyncio.sleep
        )
        self._logger = logger if logger is not None else globals()["logger"]
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_interval_seconds = retry_interval_seconds
        self.subject = subject

        # 默认 SMTP 连接参数（构造函数优先，其次环境变量，最后本地开发默认值）。
        # 这些仅在使用默认 sender 时生效；构造/导入期不建立任何连接。
        self.smtp_host = smtp_host or os.getenv("SMTP_HOST", "localhost")
        self.smtp_port = smtp_port or int(os.getenv("SMTP_PORT", "25"))
        self.smtp_username = smtp_username or os.getenv("SMTP_USERNAME")
        self.smtp_password = smtp_password or os.getenv("SMTP_PASSWORD")
        if smtp_use_tls is None:
            self.smtp_use_tls = os.getenv("SMTP_USE_TLS", "false").strip().lower() in {
                "true",
                "1",
                "yes",
            }
        else:
            self.smtp_use_tls = smtp_use_tls
        self.sender_address = sender_address or os.getenv(
            "SMTP_SENDER", "no-reply@homework-upload-system.local"
        )

    def build_email_body(
        self, assignment_title: str, submitted_at: datetime, file_name: str
    ) -> str:
        """构造邮件正文（委托至模块级 :func:`build_email_body`，纯函数）。

        与 design.md「Email_Service」接口签名保持一致；具体格式见模块级函数文档。
        """
        return build_email_body(assignment_title, submitted_at, file_name)

    async def _smtp_send(self, recipient: str, body: str) -> None:
        """默认“单次发送”实现：通过 aiosmtplib 发送一封纯文本邮件。

        懒导入 aiosmtplib 并即时构造邮件，避免模块导入/服务构造阶段产生外部依赖
        或网络连接。该协程仅尝试一次；超时由调用方（:meth:`notify_submission`）以
        :func:`asyncio.wait_for` 控制，失败/异常由调用方按重试策略处理。
        """
        # 延迟导入：避免导入期对 aiosmtplib 产生硬依赖/副作用。
        import aiosmtplib
        from email.message import EmailMessage

        message = EmailMessage()
        message["From"] = self.sender_address
        message["To"] = recipient
        message["Subject"] = self.subject
        message.set_content(body)

        await aiosmtplib.send(
            message,
            hostname=self.smtp_host,
            port=self.smtp_port,
            username=self.smtp_username,
            password=self.smtp_password,
            use_tls=self.smtp_use_tls,
        )

    async def notify_submission(
        self, submission: SubmissionRecord, student_email: Optional[str]
    ) -> None:
        """提交成功后异步发送通知邮件（需求 11.1、11.3、11.4、11.6）。

        行为：

        * **邮箱为空**（``None`` 或仅空白字符）：跳过发送，记录一条同时包含
          ``submission_id`` 与原因 “邮箱缺失” 的日志（需求 11.3 / Property 34），
          直接返回，不发起任何发送 I/O。
        * **邮箱非空**：立即发起发送（满足“60s 内发起”，需求 11.1）。每次发送尝试经
          :func:`asyncio.wait_for` 施加 :attr:`timeout_seconds`（默认 30s）超时；超时或
          任何异常均判为本次失败（需求 11.4）。失败后依 :func:`next_attempt_schedule`
          以 :attr:`retry_interval_seconds`（默认 10s）间隔最多重试 :attr:`max_retries`
          （默认 2）次，累计尝试 ≤ 3（需求 11.5）。
        * **全部尝试失败**：记录一条含 ``submission_id`` 与失败原因的发送失败日志，并
          **正常返回**（绝不抛出），从而保持已创建的提交记录有效、不回滚（需求 11.6 /
          Property 36）。

        本方法对任何发送侧错误均不向调用方传播，调用方（提交流程）无需感知发送结果。
        """
        # —— 需求 11.3：邮箱为空 -> 跳过并记日志（Property 34）。
        if student_email is None or not student_email.strip():
            self._logger.info(
                "跳过发送提交通知邮件：submission_id=%s reason=%s",
                submission.submission_id,
                EMAIL_MISSING_REASON,
            )
            return

        recipient = student_email.strip()
        body = self.build_email_body(
            submission.assignment_title, submission.submitted_at, submission.file_name
        )

        # 重试调度：首次发送 + 每项间隔对应一次重试（需求 11.5）。
        schedule = next_attempt_schedule(
            max_retries=self.max_retries,
            interval_seconds=self.retry_interval_seconds,
        )
        total_attempts = len(schedule) + 1  # 首次发送 + 重试次数（默认 3）。
        last_error: Optional[BaseException] = None

        for attempt in range(1, total_attempts + 1):
            try:
                # 需求 11.4：单次发送 30s 内未收到成功响应判失败。
                await asyncio.wait_for(
                    self._sender(recipient, body), timeout=self.timeout_seconds
                )
                # 发送成功：直接返回（无需记录失败日志）。
                return
            except asyncio.TimeoutError as exc:  # noqa: PERF203 - 需逐次捕获以重试
                last_error = exc
                self._logger.warning(
                    "提交通知邮件发送超时：submission_id=%s attempt=%d/%d timeout=%ds",
                    submission.submission_id,
                    attempt,
                    total_attempts,
                    self.timeout_seconds,
                )
            except Exception as exc:  # 任何发送异常均判为本次失败并重试。
                last_error = exc
                self._logger.warning(
                    "提交通知邮件发送失败：submission_id=%s attempt=%d/%d reason=%s",
                    submission.submission_id,
                    attempt,
                    total_attempts,
                    exc,
                )

            # 若仍有后续重试，按调度等待相应间隔后再试。
            if attempt <= len(schedule):
                await self._sleep(schedule[attempt - 1])

        # —— 需求 11.6：累计尝试均失败 -> 记录失败日志并保持提交有效（不抛出/不回滚）。
        self._logger.error(
            "提交通知邮件最终发送失败：submission_id=%s attempts=%d reason=%s",
            submission.submission_id,
            total_attempts,
            last_error,
        )
