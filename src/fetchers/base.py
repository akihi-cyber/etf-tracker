"""数据获取器基类"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class FundDataPoint:
    """一条基金/ETF 数据记录"""
    code: str
    name: str
    date: str            # "2026-06-17"
    net_value: float     # 单位净值（基金）/ 收盘价（ETF）
    acc_value: float     # 累计净值（基金）/ 0（ETF）
    daily_change: float  # 日涨跌幅（%）
    volume: float = 0.0  # 成交量（ETF 专用，基金填 0）
    source: str = ""     # 数据来源标识


class BaseFetcher(ABC):
    """抽象获取器"""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    @abstractmethod
    def fetch(self, code: str, name: str, fund_type: str) -> FundDataPoint | None:
        """获取单只基金/ETF 最新数据。失败返回 None"""
        ...

    def _clean_change(self, raw: str | float) -> float:
        """统一处理涨跌幅：转 float，去百分号"""
        if isinstance(raw, float | int):
            return float(raw)
        return float(raw.replace("%", "").strip())
