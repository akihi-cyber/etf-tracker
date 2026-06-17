"""
兜底获取器

当主数据源失败时，通过以下方式兜底：
1. 新浪财经基金 API（备选1）
2. 天天基金页面抓取（备选2）

稳定性排序：eastmoney_fund > 新浪API > 页面抓取
"""

import re
import requests
from .base import BaseFetcher, FundDataPoint

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
}

# 新浪基金净值 API
SINA_FUND_URL = "https://stock.finance.sina.com.cn/fundinfo/api/openapi.php/CaihuiFundInfoService.getNav"

# 天天基金页面（HTML 方式兜底）
TTJJ_PAGE = "https://fund.eastmoney.com/f10/jjjz_{code}.html"


class FallbackFetcher(BaseFetcher):
    """兜底获取器"""

    def fetch(self, code: str, name: str, fund_type: str) -> FundDataPoint | None:
        if fund_type == "etf":
            return self._fetch_etf_sina(code, name)

        # 基金：先试试新浪 API
        point = self._fetch_fund_sina(code, name)
        if point:
            return point

        # 再试试页面抓取
        point = self._fetch_fund_page(code, name)
        if point:
            return point

        return None

    # ── 新浪基金净值 API ──

    def _fetch_fund_sina(self, code: str, name: str) -> FundDataPoint | None:
        """新浪基金 API（基金净值）"""
        params = {
            "callback": "jQuery",
            "fund": code,
            "page": 1,
            "num": 1,
            "sort": "nav_date",
            "asc": "desc",
        }
        try:
            resp = requests.get(
                SINA_FUND_URL,
                params=params,
                headers=HEADERS,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            # 去掉 callback 包裹
            match = re.search(r"jQuery\((.+)\)", resp.text, re.DOTALL)
            if not match:
                return None

            import json
            data = json.loads(match.group(1))
            result = data.get("result", {})
            nav_list = result.get("data", [])
            if not nav_list:
                return None
            latest = nav_list[0]
            return FundDataPoint(
                code=code,
                name=name,
                date=latest.get("nav_date", ""),
                net_value=float(latest.get("nav", 0)),
                acc_value=float(latest.get("accumulated_nav", 0) or 0),
                daily_change=float(latest.get("daily_profit", 0) or 0),
                source="sina-fund-api",
            )
        except Exception as e:
            print(f"  ⚠ 新浪基金API失败 [{code}]: {e}")
            return None

    # ── 天天基金页面抓取（终极兜底）──

    def _fetch_fund_page(self, code: str, name: str) -> FundDataPoint | None:
        """抓取天天基金净值页面的表格数据（HTML 解析）"""
        try:
            resp = requests.get(
                TTJJ_PAGE.format(code=code),
                headers=HEADERS,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            resp.encoding = "utf-8"

            text = resp.text

            # 从页面提取表格中的第一行数据
            # 查找 <tr>... 其中包含日期、单位净值、累计净值、日增长率
            rows = re.findall(
                r"<tr>.*?<td>(\d{4}-\d{2}-\d{2})</td>.*?"
                r"<td[^>]*>([\d.]+)</td>.*?"
                r"<td[^>]*>([\d.]+)</td>.*?"
                r"<td[^>]*>([-\d.]+)%?</td>",
                text,
                re.DOTALL,
            )
            if not rows:
                return None

            date, dwjz, ljjz, change = rows[0]
            return FundDataPoint(
                code=code,
                name=name,
                date=date.strip(),
                net_value=float(dwjz.strip()),
                acc_value=float(ljjz.strip()),
                daily_change=float(change.strip()),
                source="ttjj-page",
            )
        except Exception as e:
            print(f"  ⚠ 天天基金页面抓取失败 [{code}]: {e}")
            return None

    # ── ETF 兜底：新浪行情 ──

    def _fetch_etf_sina(self, code: str, name: str) -> FundDataPoint | None:
        """新浪 ETF 行情（备用）"""
        # 判断交易所代码
        # 上海ETF 代码以 5 开头，深圳以 1/2 开头（ETF 多以 159 开头）
        market = 1 if code.startswith(("159", "16")) else 0
        sina_url = f"https://hq.sinajs.cn/list=s{market}{code}"
        try:
            resp = requests.get(
                sina_url,
                headers={**HEADERS, "Referer": "https://finance.sina.com.cn"},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            # 返回 GBK 编码
            resp.encoding = "gbk"
            # 格式: var hq_str_sz159949="创业板50,0.857,...
            parts = resp.text.split('"')
            if len(parts) < 2:
                return None
            fields = parts[1].split(",")
            if len(fields) < 32:
                return None

            # 新浪ETF行情字段: 名称, 开盘, 昨收, 当前价, 最高, 最低, ...
            price = float(fields[3]) if fields[3] else 0
            close = float(fields[2]) if fields[2] else price
            change = ((price - close) / close * 100) if close else 0
            volume = float(fields[8]) if len(fields) > 8 else 0  # 成交量

            return FundDataPoint(
                code=code,
                name=name,
                date="",  # 新浪不直接返回日期，用在 validator 中补充
                net_value=price,
                acc_value=0,
                daily_change=round(change, 2),
                volume=volume,
                source="sina-etf-hq",
            )
        except Exception as e:
            print(f"  ⚠ 新浪ETF行情失败 [{code}]: {e}")
            return None
