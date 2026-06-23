"""
大盘指数 / 商品行情获取器

支持：
  - 中国A股指数（东方财富行情API）：科创50、中证A500 等
  - 美股指数（雅虎财经API）：标普500、纳斯达克100 等
  - 黄金现货（东方财富行情API）：AU9999

无需额外依赖，只使用 requests + PyYAML（已存在）。
"""

import json
import re
import requests
from datetime import datetime, timezone, timedelta

from .base import FundDataPoint

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
}

# 东方财富行情 API（中国指数 + 黄金）
EM_QUOTE_URL = "https://push2.eastmoney.com/api/qt/stock/get"

# 雅虎财经 API（美股指数）
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"


class IndexFetcher:
    """大盘指数/商品行情获取器"""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    def fetch(self, code: str, name: str, market: str) -> FundDataPoint | None:
        """根据 market 类型路由到对应获取方法"""
        if market == "cn_index":
            return self._fetch_cn_index(code, name)
        elif market == "us_index":
            return self._fetch_us_index(code, name)
        elif market == "cn_gold":
            return self._fetch_cn_gold(code, name)
        else:
            print(f"  ⚠ 未知市场类型: {market} (code={code})")
            return None

    # ── 中国A股指数 ──────────────────────────────────

    def _fetch_cn_index(self, code: str, name: str) -> FundDataPoint | None:
        """通过东方财富行情 API 获取A股指数数据"""
        # secid 规则：上交所 1.xxx, 深交所 0.xxx, CSI指数尝试0.xxx
        if code.startswith(("399", "159")):
            secid = f"0.{code}"
        else:
            secid = f"1.{code}"

        params = {
            "secid": secid,
            "fields": "f43,f44,f45,f46,f47,f48,f50,f57,f58,f169,f170,f171,f172",
        }

        try:
            resp = requests.get(
                EM_QUOTE_URL,
                params=params,
                headers=HEADERS,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json().get("data", {})
            if not data or not data.get("f43"):
                return None

            price = float(data.get("f43", 0))
            change_pct = float(data.get("f48", 0)) if data.get("f48") else 0.0
            volume = float(data.get("f169", 0)) if data.get("f169") else 0.0  # 成交量(手)

            now = datetime.now(timezone(timedelta(hours=8)))
            return FundDataPoint(
                code=code,
                name=name,
                date=now.strftime("%Y-%m-%d"),
                net_value=round(price, 2),
                acc_value=0,
                daily_change=round(change_pct, 2),
                volume=round(volume, 0),
                source="eastmoney-index-hq",
            )
        except Exception as e:
            print(f"  ⚠ 东方财富指数行情失败 [{name}]: {e}")
            return None

    # ── 美股指数 ──────────────────────────────────

    def _fetch_us_index(self, code: str, name: str) -> FundDataPoint | None:
        """通过雅虎财经 API 获取美股指数数据"""
        # ^ 需要 URL 编码
        symbol = code.replace("^", "%5E")

        try:
            resp = requests.get(
                YAHOO_CHART_URL.format(symbol=symbol),
                params={"interval": "1d", "range": "5d"},
                headers=HEADERS,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            resp_json = resp.json()

            result = resp_json.get("chart", {}).get("result", [])
            if not result:
                # 试试备用 symbol 格式（去掉 ^）
                alt_symbol = code.lstrip("^")
                resp2 = requests.get(
                    YAHOO_CHART_URL.format(symbol=alt_symbol),
                    params={"interval": "1d", "range": "5d"},
                    headers=HEADERS,
                    timeout=self.timeout,
                )
                resp2.raise_for_status()
                result = resp2.json().get("chart", {}).get("result", [])

            if not result:
                return None

            meta = result[0].get("meta", {})
            timestamps = result[0].get("timestamp", [])
            indicators = result[0].get("indicators", {})
            quotes = indicators.get("quote", [{}])[0] if indicators.get("quote") else {}
            closes = quotes.get("close", []) or []
            volumes = quotes.get("volume", []) or []

            if not closes:
                return None

            # 确定最后一个完整交易日
            # 如果当天（US东部时间）有部分数据，用前一天
            last_complete_idx = len(closes) - 1
            if timestamps:
                now_ny = datetime.now(timezone.utc) - timedelta(hours=4)  # EDT ≈ UTC-4
                today_ny = now_ny.date()
                last_ts = datetime.fromtimestamp(timestamps[-1], tz=timezone.utc)
                last_day = (last_ts - timedelta(hours=4)).date()
                # 如果最后一条数据是今天（EDT），取前一条
                if last_day == today_ny and len(closes) > 1 and closes[-1] is None:
                    last_complete_idx = -2

            # 找到最后一个有值的收盘价
            closest_idx = last_complete_idx
            while closest_idx >= 0 and closes[closest_idx] is None:
                closest_idx -= 1
            if closest_idx < 0:
                return None

            close_price = float(closes[closest_idx])
            prev_close = float(meta.get("chartPreviousClose", close_price) or close_price)
            if prev_close > 0:
                change_pct = (close_price - prev_close) / prev_close * 100
            else:
                change_pct = 0.0

            volume = float(volumes[closest_idx]) if volumes and closest_idx < len(volumes) and volumes[closest_idx] else 0.0

            # 日期
            date_str = ""
            if timestamps and closest_idx < len(timestamps) and timestamps[closest_idx]:
                dt = datetime.fromtimestamp(timestamps[closest_idx], tz=timezone.utc)
                date_str = dt.strftime("%Y-%m-%d")

            return FundDataPoint(
                code=code,
                name=name,
                date=date_str,
                net_value=round(close_price, 2),
                acc_value=0,
                daily_change=round(change_pct, 2),
                volume=round(volume, 0),
                source="yahoo-finance",
            )
        except Exception as e:
            print(f"  ⚠ 雅虎财经失败 [{name}]: {e}")
            return None

    # ── 黄金现货 ──────────────────────────────────

    def _fetch_cn_gold(self, code: str, name: str) -> FundDataPoint | None:
        """通过东方财富行情 API 获取黄金（AU9999）行情"""
        secid = f"1.{code}"

        params = {
            "secid": secid,
            "fields": "f43,f44,f45,f46,f47,f48,f50,f57,f58,f169,f170,f171,f172",
        }

        try:
            resp = requests.get(
                EM_QUOTE_URL,
                params=params,
                headers=HEADERS,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json().get("data", {})
            if not data or not data.get("f43"):
                return None

            price = float(data.get("f43", 0))
            change_pct = float(data.get("f48", 0)) if data.get("f48") else 0.0
            volume = float(data.get("f169", 0)) if data.get("f169") else 0.0

            now = datetime.now(timezone(timedelta(hours=8)))
            return FundDataPoint(
                code=code,
                name=name,
                date=now.strftime("%Y-%m-%d"),
                net_value=round(price, 2),
                acc_value=0,
                daily_change=round(change_pct, 2),
                volume=round(volume, 0),
                source="eastmoney-gold-hq",
            )
        except Exception as e:
            print(f"  ⚠ 东方财富黄金行情失败 [{name}]: {e}")
            return None


def fetch_all_indices(
    indices_cfg: list[dict],
    commodities_cfg: list[dict],
    timeout: int = 15,
) -> dict[str, FundDataPoint]:
    """
    批量获取所有指数和商品行情

    Returns:
        {code: FundDataPoint, ...} 映射
    """
    fetcher = IndexFetcher(timeout=timeout)
    results: dict[str, FundDataPoint] = {}

    # 获取指数
    for item in indices_cfg:
        code = item["code"]
        name = item["name"]
        market = item["market"]
        print(f"  📊 [{name}] 获取中...")
        point = fetcher.fetch(code, name, market)
        if point:
            results[code] = point
            direction = "🟢" if point.daily_change >= 0 else "🔴"
            print(f"    ✅ {name}: {point.net_value} ({direction} {point.daily_change:+.2f}%)")
        else:
            print(f"    ❌ {name}: 获取失败")

    # 获取商品
    for item in commodities_cfg:
        code = item["code"]
        name = item["name"]
        market = item["market"]
        print(f"  🥇 [{name}] 获取中...")
        point = fetcher.fetch(code, name, market)
        if point:
            results[f"commodity:{code}"] = point
            direction = "🟢" if point.daily_change >= 0 else "🔴"
            print(f"    ✅ {name}: {point.net_value} ({direction} {point.daily_change:+.2f}%)")
        else:
            print(f"    ❌ {name}: 获取失败")

    return results
