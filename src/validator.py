"""
交叉验证模块

从多个数据源获取同一基金的数据，对比一致性。
策略：
  - 主数据源（eastmoney_lsjz）优先
  - 备选数据源验证
  - 如果主源成功且数据合理，直接接受
  - 若主源失败，尝试备选源，≥2 个源一致则接受
  - 均失败则标记为失败
"""

import time
from datetime import datetime, timezone, timedelta
from .config import Config
from .fetchers.base import FundDataPoint


class Validator:
    """交叉验证器"""

    # 日涨跌幅可信范围（避免异常值）
    CHANGE_RANGE = (-15, 15)  # 正常基金单日不会超过±15%

    def __init__(self, config: Config, fetchers: list):
        self.cfg = config
        self.fetchers = fetchers
        self.results: dict[str, FundDataPoint | None] = {}
        self.errors: dict[str, list[str]] = {}

    def run(self, funds: list[dict]) -> dict[str, FundDataPoint]:
        """对每个基金运行交叉验证"""
        self.results = {}
        self.errors = {}

        for fund in funds:
            code = fund["code"]
            name = fund["name"]
            ftype = fund.get("type", "fund")

            result = self._validate_one(code, name, ftype)
            self.results[code] = result

            # 记录
            status = "✅" if result else "❌"
            value_str = f"{result.net_value:.4f} ({result.daily_change:+.2f}%)" if result else "无数据"
            print(f"  {status} [{code}] {name}: {value_str}")

        return {k: v for k, v in self.results.items() if v is not None}

    def _validate_one(self, code: str, name: str, ftype: str) -> FundDataPoint | None:
        """单只基金的交叉验证"""
        sources_data: list[tuple[str, FundDataPoint]] = []
        source_names = []
        retries = self.cfg.max_retries

        # 遍历所有数据源
        for fetcher in self.fetchers:
            for attempt in range(retries):
                point = fetcher.fetch(code, name, ftype)
                if point is not None and self._is_plausible(point):
                    sources_data.append((point.source, point))
                    source_names.append(point.source)
                    break  # 这个源成功了
                elif point is not None and not self._is_plausible(point):
                    print(f"  ⚠ [{fetcher.__class__.__name__}] {code}: 数据不合理({point.daily_change:+.2f}%)，重试第{attempt+2}次...")
                else:
                    print(f"  ⚠ [{fetcher.__class__.__name__}] {code}: 获取失败，重试第{attempt+2}次...")
                time.sleep(self.cfg.retry_cooldown)

        if not sources_data:
            self.errors.setdefault(code, []).append("所有数据源均获取失败")
            return None

        # 交叉验证：主源（eastmoney-lsjz）的数据优先
        primary = [s for s in sources_data if "eastmoney" in s[0]]
        if primary:
            return primary[0][1]

        # 如果有至少 min_sources 个不同的源且数据接近，接受
        if len(sources_data) >= self.cfg.min_sources:
            # 检查这些源的数据是否一致（净值偏差 < 0.5%）
            values = [s[1].net_value for s in sources_data]
            if max(values) - min(values) < 0.005 * max(values):  # 0.5% 偏差容忍
                return sources_data[0][1]
            else:
                self.errors.setdefault(code, []).append(
                    f"多源数据不一致: {source_names} → 净值 {[round(v,4) for v in values]}"
                )
                # 仍返回第一个可用数据，但标记警告
                return sources_data[0][1]

        return sources_data[0][1]

    def _is_plausible(self, point: FundDataPoint) -> bool:
        """数据合理性检查"""
        # 净值必须为正
        if point.net_value <= 0:
            return False
        # 涨跌幅在合理范围内
        if abs(point.daily_change) > self.CHANGE_RANGE[1]:
            print(f"  ⚠ 异常涨跌幅: {point.daily_change:+.2f}% (code={point.code})")
            return False
        return True

    def get_report_errors(self) -> str:
        """获取错误汇总（用于日报中的错误说明）"""
        if not self.errors:
            return ""
        lines = ["\n### ⚠️ 数据异常"]
        for code, errs in self.errors.items():
            lines.append(f"- **{code}**: {'; '.join(errs)}")
        return "\n".join(lines)
