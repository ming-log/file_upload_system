"""统一时钟：项目所有业务时间均采用**北京时间**（Asia/Shanghai, UTC+8）。

设计约定（全系统一致）：

* 业务"现在"由 :func:`now_cn` 提供（aware，带 UTC+8 时区），用于令牌签发等需要
  真实瞬时的场景。
* 持久化与比较统一使用**北京时间的 naive datetime**（:func:`now_cn_naive`）：
  数据库列不带时区，其数值即北京墙钟时间。截止时间、提交时间、创建时间、序列化
  输出、邮件/CSV 中的时间字符串均为北京时间，确保比较与显示口径一致。
* 前端 ``<input type="datetime-local">`` 的取值本身就是北京墙钟，经
  :func:`to_naive_cn` 原样保留；前端展示用 ``new Date(...).toLocaleString('zh-CN')``
  在北京时区浏览器下即显示北京时间。

为何不用 UTC 存储：本系统面向国内学校，统一以北京时间为唯一口径可消除"存 UTC、
显示本地"导致的 8 小时偏差，并使 ``datetime-local`` 输入/回显天然对齐。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

__all__ = ["CHINA_TZ", "now_cn", "now_cn_naive", "to_naive_cn"]

#: 北京时区（UTC+8，无夏令时）。
CHINA_TZ = timezone(timedelta(hours=8), "Asia/Shanghai")


def now_cn() -> datetime:
    """返回当前北京时间（aware，UTC+8）。"""
    return datetime.now(CHINA_TZ)


def now_cn_naive() -> datetime:
    """返回当前北京时间的 naive datetime（去除时区，用于存储与比较）。"""
    return now_cn().replace(tzinfo=None)


def to_naive_cn(value: datetime) -> datetime:
    """将 datetime 归一化为北京时间的 naive datetime。

    * aware datetime：先转换到北京时区，再去除 tzinfo；
    * naive datetime：视为已是北京墙钟时间，原样返回。
    """
    if value.tzinfo is not None:
        return value.astimezone(CHINA_TZ).replace(tzinfo=None)
    return value
