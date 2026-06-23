"""
日报生成器 ── 生成美观的 Markdown 日报

支持基金净值 + 大盘指数 + 商品行情三板块。
"""

from datetime import datetime, timezone, timedelta
from .config import Config
from .fetchers.base import FundDataPoint


def get_beijing_time() -> datetime:
    """获取当前北京时间"""
    return datetime.now(timezone(timedelta(hours=8)))


_FUND_SOURCE_ICONS = {
    "eastmoney-lsjz": "📡",
    "eastmoney-fundgz": "📡",
    "sina-fund-api": "🔄",
    "ttjj-page": "🌐",
    "sina-etf-hq": "🔄",
}


def _format_change(change: float) -> str:
    """格式化涨跌幅 + 颜色符号"""
    direction = "🟢" if change >= 0 else "🔴"
    return f"{direction} {change:+.2f}%"


def _volume_str(vol: float) -> str:
    """格式化成交量，显示为可读形式"""
    if vol <= 0:
        return "—"
    if vol >= 100000000:
        return f"{vol / 100000000:.2f}亿"
    elif vol >= 10000:
        return f"{vol / 10000:.2f}万"
    else:
        return f"{vol:.0f}"


def generate_report(
    cfg: Config,
    results: dict[str, FundDataPoint],
    index_results: dict[str, FundDataPoint],
    ai_analysis: str | None,
    errors: str,
) -> str:
    """
    生成 Markdown 格式日报

    Args:
        cfg: 配置
        results: code → FundDataPoint 映射（基金/ETF）
        index_results: code→FundDataPoint 映射（指数+商品）
        ai_analysis: AI 分析文本
        errors: 错误汇总
    """
    now = get_beijing_time()
    today = now.strftime("%Y-%m-%d")
    weekday = ["一", "二", "三", "四", "五", "六", "日"][now.weekday()]

    lines = [
        f"## 📊 基金日报 — {today}（周{weekday}）",
        "",
        f"_生成时间：{now.strftime('%H:%M')} 北京时间_",
        "",
        "---",
        "",
        "### 📋 今日净值",
        "",
        "| 基金 | 代码 | 单位净值 | 日涨跌幅 | 对应指数 | 数据源 |",
        "|------|------|---------|:-------:|:--------:|:------:|",
    ]

    for fund in cfg.funds:
        code = fund["code"]
        name = fund["name"]
        point = results.get(code)

        if point:
            change_str = _format_change(point.daily_change)
            source_icon = _FUND_SOURCE_ICONS.get(point.source, "❓")
            # 找对应指数名
            matched_idx = ""
            for p in index_results.values():
                if p:
                    kw = p.name.replace("上证", "").replace("中证", "")
                    if kw in name:
                        matched_idx = kw
                        break
            lines.append(
                f"| {name} | `{code}` | {point.net_value:.4f} | {change_str} | {matched_idx} | {source_icon} {point.source} |"
            )
        else:
            lines.append(f"| {name} | `{code}` | — | ⚠️ 无数据 | — | ⛔ |")

    # ── 大盘指数板块 ──────────────────────────────────
    if cfg.indices and any(f"index:{i['code']}" in index_results or i["code"] in index_results for i in cfg.indices):
        lines.extend([
            "",
            "---",
            "",
            "### 📈 大盘行情",
            "",
            "| 指数 | 代码 | 收盘价 | 涨跌幅 | 成交量 | 数据源 |",
            "|------|------|:-----:|:-----:|:-----:|:------:|",
        ])
        for idx_cfg in cfg.indices:
            code = idx_cfg["code"]
            name = idx_cfg["name"]
            point = index_results.get(code)
            if point:
                vol_str = _volume_str(point.volume)
                source_icons = {
                    "eastmoney-index-hq": "📡",
                    "yahoo-finance": "🌍",
                }.get(point.source, "❓")
                lines.append(
                    f"| {name} | `{code}` | {point.net_value:.2f} | {_format_change(point.daily_change)} | {vol_str} | {source_icons} {point.source} |"
                )
            else:
                lines.append(f"| {name} | `{code}` | — | ⚠️ 无数据 | — | ⛔ |")

    # ── 黄金板块 ─────────────────────────────────────
    commodity_prefix = "commodity:"
    gold_items = {k: v for k, v in index_results.items() if k.startswith(commodity_prefix)}
    if gold_items:
        lines.extend([
            "",
            "---",
            "",
            "### 🥇 商品行情",
            "",
            "| 品种 | 代码 | 价格 | 涨跌幅 | 成交量 | 数据源 |",
            "|------|------|:----:|:-----:|:-----:|:------:|",
        ])
        for cfg_item in cfg.commodities:
            full_code = f"{commodity_prefix}{cfg_item['code']}"
            point = gold_items.get(full_code)
            if point:
                lines.append(
                    f"| {point.name} | `{cfg_item['code']}` | {point.net_value:.2f} | {_format_change(point.daily_change)} | {_volume_str(point.volume)} | 📡 {point.source} |"
                )
            else:
                lines.append(f"| {cfg_item['name']} | `{cfg_item['code']}` | — | ⚠️ 无数据 | — | ⛔ |")

    # ── 组合明细 ─────────────────────────────────────
    lines.extend([
        "",
        "---",
        "",
        "### ℹ️ 各基金详情",
        "",
    ])
    for fund in cfg.funds:
        code = fund["code"]
        name = fund["name"]
        point = results.get(code)
        if point:
            lines.extend([
                f"- **{name}**（`{code}`）",
                f"  - 单位净值：**{point.net_value:.4f}**",
                f"  - 累计净值：**{point.acc_value:.4f}**",
                f"  - 日涨跌幅：**{point.daily_change:+.2f}%**",
                f"  - 数据来源：{point.source}",
            ])
            if point.volume > 0:
                lines.append(f"  - 成交量：{point.volume:.0f}")
            # 对应指数提示：按名称匹配
            idx_point = None
            for p in index_results.values():
                if p and (p.name in name or name in p.name):
                    # 检查是否有实质关联（keyword overlap）
                    kw = p.name.replace("上证", "").replace("中证", "")
                    if kw in name:
                        idx_point = p
                        break
            if idx_point:
                lines.append(f"  - 对应指数：{idx_point.name} {_format_change(idx_point.daily_change)}")
            lines.append("")

    # ── AI 分析 ──────────────────────────────────────
    if ai_analysis:
        lines.extend([
            "---",
            "",
            "### 🧠 AI 分析",
            "",
            ai_analysis,
            "",
        ])

    # ── 错误信息 ─────────────────────────────────────
    if errors:
        lines.append(errors)
        lines.append("")

    # ── 页脚 ─────────────────────────────────────────
    lines.extend([
        "---",
        "",
        f"🔄 _由 ETF-Tracker 自动生成 · {now.strftime('%Y-%m-%d %H:%M')} CST_",
        "",
    ])

    return "\n".join(lines)


def generate_plaintext_report(report_md: str) -> str:
    """
    将 Markdown 日报转成纯文本（用于邮件纯文本 fallback）
    简单去除 markdown 格式
    """
    import re
    text = report_md
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)  # 去加粗
    text = re.sub(r"\|.*?\|", "", text, flags=re.MULTILINE)  # 去表格
    text = re.sub(r"^[-—]{3,}$", "", text, flags=re.MULTILINE)  # 去分隔线
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
