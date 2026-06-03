"""登录验证码服务（Captcha_Service）。

为满足「学生登录时需输入验证码」的需求，本模块提供一个零外部依赖的图形验证码
服务：

* :meth:`CaptchaService.generate` —— 生成一个验证码挑战，返回 ``(captcha_id,
  image_data_url)``。``captcha_id`` 为随机标识，``image_data_url`` 是一张内嵌
  验证码字符的 SVG 图（``data:image/svg+xml;base64,...``），前端可直接用于
  ``<img src>``。验证码文本与过期时间被保存在进程内存中（以 ``captcha_id`` 为键）。
* :meth:`CaptchaService.verify` —— 校验用户输入是否与 ``captcha_id`` 对应的文本
  一致（不区分大小写），且未过期。验证码**一次性**使用：无论成功失败，校验后即从
  存储中移除，防止重放。

设计说明：
* **零依赖**：使用 SVG 而非位图，无需 Pillow 等图像库即可生成带干扰线/噪点的
  可读验证码。
* **内存存储**：验证码挑战保存在进程内字典中，适合单进程开发/演示部署。多实例
  部署时应替换为共享存储（如 Redis）。
* **可测试**：``generate`` / ``verify`` 接受可注入的 ``now`` 与随机源，便于确定性
  测试；过期时间通过 :data:`CAPTCHA_TTL_SECONDS` 控制。
"""

from __future__ import annotations

import base64
import random
import secrets
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

__all__ = [
    "CAPTCHA_TTL_SECONDS",
    "CAPTCHA_LENGTH",
    "CaptchaService",
]

#: 验证码有效期（秒）。超过该时长后校验一律失败。
CAPTCHA_TTL_SECONDS: int = 300

#: 验证码字符个数。
CAPTCHA_LENGTH: int = 4

#: 验证码字符集（去除易混淆字符 0/O/1/I/l）。
_CAPTCHA_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


@dataclass
class _Challenge:
    """内存中的验证码挑战记录。"""

    text: str
    expires_at: float


def _random_text(length: int, rng: random.Random) -> str:
    """生成长度为 ``length`` 的随机验证码文本。"""
    return "".join(rng.choice(_CAPTCHA_ALPHABET) for _ in range(length))


def _build_svg(text: str, rng: random.Random) -> str:
    """渲染一张包含 ``text`` 的 SVG 验证码图（带噪点与干扰线）。"""
    width, height = 120, 44
    colors = ["#2563eb", "#7c3aed", "#dc2626", "#059669", "#d97706", "#0891b2"]
    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="#f3f4f6"/>',
    ]

    # 干扰线。
    for _ in range(4):
        x1, y1 = rng.randint(0, width), rng.randint(0, height)
        x2, y2 = rng.randint(0, width), rng.randint(0, height)
        color = rng.choice(colors)
        parts.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="{color}" stroke-width="1" opacity="0.5"/>'
        )

    # 噪点。
    for _ in range(20):
        cx, cy = rng.randint(0, width), rng.randint(0, height)
        parts.append(
            f'<circle cx="{cx}" cy="{cy}" r="1" fill="{rng.choice(colors)}" opacity="0.6"/>'
        )

    # 字符（轻微旋转与位移，增加识别难度）。
    step = width // (len(text) + 1)
    for i, ch in enumerate(text):
        x = step * (i + 1)
        y = rng.randint(28, 34)
        angle = rng.randint(-25, 25)
        color = rng.choice(colors)
        parts.append(
            f'<text x="{x}" y="{y}" font-size="26" font-family="Arial,Helvetica,sans-serif" '
            f'font-weight="bold" fill="{color}" text-anchor="middle" '
            f'transform="rotate({angle} {x} {y})">{ch}</text>'
        )

    parts.append("</svg>")
    return "".join(parts)


class CaptchaService:
    """图形验证码生成与校验服务（进程内存存储，一次性使用）。

    Args:
        ttl_seconds: 验证码有效期（秒），默认 :data:`CAPTCHA_TTL_SECONDS`。
        length: 验证码字符个数，默认 :data:`CAPTCHA_LENGTH`。
        rng: 可选随机源，便于测试注入确定性随机；缺省使用模块级安全随机。
    """

    def __init__(
        self,
        *,
        ttl_seconds: int = CAPTCHA_TTL_SECONDS,
        length: int = CAPTCHA_LENGTH,
        rng: Optional[random.Random] = None,
    ) -> None:
        self.ttl_seconds = ttl_seconds
        self.length = length
        self._rng = rng or random.SystemRandom()
        self._store: Dict[str, _Challenge] = {}

    def _now(self) -> float:
        return time.time()

    def _purge_expired(self, now: float) -> None:
        """清理已过期的验证码挑战，避免内存无限增长。"""
        expired = [cid for cid, ch in self._store.items() if ch.expires_at <= now]
        for cid in expired:
            self._store.pop(cid, None)

    def generate(self, now: Optional[float] = None) -> Tuple[str, str]:
        """生成验证码挑战。

        Returns:
            ``(captcha_id, image_data_url)``：``captcha_id`` 用于后续校验；
            ``image_data_url`` 为可直接用于 ``<img src>`` 的 SVG data URL。
        """
        current = self._now() if now is None else now
        self._purge_expired(current)

        captcha_id = secrets.token_urlsafe(16)
        text = _random_text(self.length, self._rng)
        self._store[captcha_id] = _Challenge(
            text=text, expires_at=current + self.ttl_seconds
        )

        svg = _build_svg(text, self._rng)
        encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
        image_data_url = f"data:image/svg+xml;base64,{encoded}"
        return captcha_id, image_data_url

    def verify(
        self, captcha_id: Optional[str], text: Optional[str], now: Optional[float] = None
    ) -> bool:
        """校验用户输入是否匹配验证码（不区分大小写）；验证码一次性使用。

        无论成功与否，匹配的 ``captcha_id`` 都会在校验后被移除（防重放）。
        ``captcha_id`` 缺失/不存在/已过期，或文本不匹配，均返回 ``False``。
        """
        if not captcha_id or not text:
            return False

        current = self._now() if now is None else now
        challenge = self._store.pop(captcha_id, None)
        if challenge is None:
            return False
        if challenge.expires_at <= current:
            return False
        return secrets.compare_digest(challenge.text.upper(), text.strip().upper())
