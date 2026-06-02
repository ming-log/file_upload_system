"""pytest 与 Hypothesis 全局配置。

依据 design.md 的 Testing Strategy：每个属性测试至少运行 100 次迭代
（max_examples >= 100）。本文件注册并默认激活一个 ``ci`` Hypothesis
profile 以满足该要求，可通过环境变量 ``HYPOTHESIS_PROFILE`` 覆盖。
"""

from __future__ import annotations

import os

from hypothesis import HealthCheck, settings

# 每个属性测试至少运行 100 次（design.md Testing Strategy 要求）。
MIN_EXAMPLES = 100

# 默认 profile：满足 >=100 次迭代的硬性要求。
settings.register_profile(
    "ci",
    max_examples=MIN_EXAMPLES,
    deadline=None,  # 关闭单例超时，避免 CI 抖动导致误报。
    suppress_health_check=[HealthCheck.too_slow],
)

# 开发期 profile：迭代更多，更易发现反例。
settings.register_profile(
    "dev",
    max_examples=500,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)

# 快速 profile：本地烟雾验证使用（仍建议提交前跑 ci/dev）。
settings.register_profile(
    "fast",
    max_examples=25,
    deadline=None,
)

settings.load_profile(os.getenv("HYPOTHESIS_PROFILE", "ci"))
