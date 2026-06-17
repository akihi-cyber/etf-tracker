"""
日报生成器 ── 生成美观的 Markdown 日报
"""

from datetime import datetime, timezone, timedelta
from .config import Config
from .fetchers.base import FundDataPoint


def get_beijing_time() -> datetime:
    """获取当前北京时间"""
    return datetime.now(timezone(timedelta(hours=8)))


def generate_report(
    cfg: Config,
    results: dict[str, FundDataPoint],
    ai_analysis: str | None,
    errors: str,
) -> str:
    """
    生成 Markdown 格式日报

    Args:
        cfg: 配置
        results: code → FundDataPoint 映射
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
        "| 基金 | 代码 | 单位净值 | 日涨跌幅 | 数据源 |",
        "|------|------|---------|:-------:|:------:|",
    ]

    for fund in cfg.funds:
        code = fund["code"]
        name = fund["name"]
        point = results.get(code)

        if point:
            change_str = f"{point.daily_change:+.2f}%"
            # 用颜色符号表示涨跌
            direction = "🟢" if point.daily_change >= 0 else "🔴"
            change_str = f"{direction} {change_str}"
            source_icon = {"eastmoney-lsjz": "📡", "eastmoney-fundgz": "📡", "sina-fund-api": "🔄", "ttjj-page": "🌐", "sina-etf-hq": "🔄"}.get(
                point.source, "❓"
            )
            lines.append(
                f"| {name} | `{code}` | {point.net_value:.4f} | {change_str} | {source_icon} {point.source} |"
            )
        else:
            lines.append(f"| {name} | `{code}` | — | ⚠️ 无数据 | ⛔ |")

    # 组合明细
    lines.extend([
        "",
        "---",
        "",
        "### 📈 组合情况",
        "",
    ])

    # 计算组合整体表现（忽略无数据的基金）
    valid_results = {k: v for k, v in results.items() if v is not None}
    if valid_results:
        avg_change = sum(p.daily_change for p in valid_results.values()) / len(valid_results)
        total_nav = sum(p.net_value for p in valid_results.values())
        lines.append(f"- **参与计算的基金数**：{len(valid_results)} / {len(cfg.funds)}")
        lines.append(f"- **组合平均涨跌**：{avg_change:+.2f}%")
        lines.append(f"- **组合净值总和**：{total_nav:.2f}")
    else:
        lines.append("- ⚠️ 今日无有效数据")

    lines.append("")

    # 基金明细
    lines.extend([
        "### ℹ️ 各基金详情",
        "",
    ])
    for fund in cfg.funds:
        code = fund["code"]
        name = fund["name"]
        point = results.get(code)
        if point:
            lines.append(f"- **{name}**（`{code}`）")
            lines.append(f"  - 单位净值：**{point.net_value:.4f}**")
            lines.append(f"  - 累计净值：**{point.acc_value:.4f}**")
            lines.append(f"  - 日涨跌幅：**{point.daily_change:+.2f}%**")
            lines.append(f"  - 数据来源：{point.source}")
            if point.volume > 0:
                lines.append(f"  - 成交量：{point.volume:.0f}")
            lines.append("")

    # AI 分析
    if ai_analysis:
        lines.extend([
            "---",
            "",
            "### 🧠 AI 分析",
            "",
            ai_analysis,
            "",
        ])

    # 错误信息
    if errors:
        lines.append(errors)
        lines.append("")

    # 页脚
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
