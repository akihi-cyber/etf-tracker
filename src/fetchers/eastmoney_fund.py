"""
东方财富基金净值 API 获取器（主力数据源）

使用 /f10/lsjz 接口获取日净值数据。
该接口已稳定运行 5+ 年，是目前国内最稳定的基金净值来源。
"""

import json
import re
import time
import requests
from .base import BaseFetcher, FundDataPoint

# 基金净值历史接口（稳定）
LSJZ_URL = "https://api.fund.eastmoney.com/f10/lsjz"

# 基金实时估算接口（盘中可用，盘后返回当日净值）
GZ_URL = "https://fundgz.1234567.com.cn/js/{code}.js"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Referer": "https://fund.eastmoney.com/",
}


class EastMoneyFundFetcher(BaseFetcher):
    """基金净值获取器（场外基金专用）"""

    def fetch(self, code: str, name: str, fund_type: str) -> FundDataPoint | None:
        if fund_type != "fund":
            return None  # 只处理基金类型

        # 策略一：通过 lsjz 接口获取最新净值（最稳定）
        point = self._fetch_lsjz(code, name)
        if point:
            return point

        # 策略二：通过 fundgz 实时接口获取最新估算/净值
        point = self._fetch_gz(code, name)
        if point:
            return point

        return None

    def _fetch_lsjz(self, code: str, name: str) -> FundDataPoint | None:
        """通过历史净值接口获取最新一天的数据"""
        params = {
            "fundCode": code,
            "pageIndex": 1,
            "pageSize": 3,  # 取最近 3 条，确保拿到最新
        }
        try:
            resp = requests.get(
                LSJZ_URL,
                params=params,
                headers=HEADERS,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("ErrCode") != 0:
                return None

            lsjz_list = data.get("Data", {}).get("LSJZList", [])
            if not lsjz_list:
                return None

            latest = lsjz_list[0]
            return FundDataPoint(
                code=code,
                name=name,
                date=latest["FSRQ"],
                net_value=float(latest["DWJZ"]),
                acc_value=float(latest.get("LJJZ", latest["DWJZ"])),
                daily_change=float(latest.get("JZZZL", 0) or 0),
                source="eastmoney-lsjz",
            )
        except Exception as e:
            print(f"  ⚠ lsjz 接口失败 [{code}]: {e}")
            return None

    def _fetch_gz(self, code: str, name: str) -> FundDataPoint | None:
        """通过 fundgz 实时估算接口获取"""
        try:
            resp = requests.get(
                GZ_URL.format(code=code),
                headers=HEADERS,
                timeout=self.timeout,
            )
            resp.raise_for_status()

            # 响应格式: jsonpgz({...});
            match = re.search(r"jsonpgz\((.+)\)", resp.text)
            if not match:
                return None

            data = json.loads(match.group(1))
            return FundDataPoint(
                code=code,
                name=name,
                date=data.get("jzrq", ""),
                net_value=float(data.get("dwjz", 0)),
                acc_value=float(data.get("ljjz", 0) or 0),
                daily_change=float(data.get("gszzl", 0) or 0),
                source="eastmoney-fundgz",
            )
        except Exception as e:
            print(f"  ⚠ fundgz 接口失败 [{code}]: {e}")
            return None
