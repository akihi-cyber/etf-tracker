"""
AI 分析模块 —— 调用 DeepSeek API 对基金净值数据进行简短分析

启用条件：
  1. config/settings.yaml 中 ai_analysis.enabled = true
  2. GitHub Secrets 中设置了 AI_API_KEY
"""

import json
import requests
from datetime import datetime, timezone, timedelta

from .config import Config
from .fetchers.base import FundDataPoint

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"


def analyze(cfg: Config, results: dict[str, FundDataPoint]) -> str | None:
    """调用 DeepSeek 对当日净值数据进行分析"""
    if not cfg.ai_enabled:
        return None

    if not cfg.ai_api_key:
        return "AI 分析已启用但未配置 API Key（请设置 GitHub Secret: AI_API_KEY）"

    # 构造 prompt
    prompt = _build_prompt(cfg, results)

    # 调用 DeepSeek API
    headers = {
        "Authorization": f"Bearer {cfg.ai_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是一位专业的基金投资分析师，语言简洁、客观。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
        "max_tokens": 800,
    }

    try:
        resp = requests.post(
            DEEPSEEK_URL,
            json=payload,
            headers=headers,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        print("  AI 分析完成")
        return content.strip()
    except requests.exceptions.Timeout:
        print("  AI API 请求超时")
        return "AI 分析请求超时，请稍后重试。"
    except requests.exceptions.HTTPError as e:
        if resp.status_code == 401:
            return "AI API Key 无效，请检查 GitHub Secret: AI_API_KEY"
        elif resp.status_code == 429:
            return "AI API 调用频率过高/额度用尽，请稍后再试。"
        return f"AI API 请求失败 (HTTP {resp.status_code}): {e}"
    except (KeyError, json.JSONDecodeError) as e:
        return f"AI API 响应解析失败: {e}"
    except Exception as e:
        return f"AI 分析异常: {e}"


def _build_prompt(cfg: Config, results: dict[str, FundDataPoint]) -> str:
    """构造发给 DeepSeek 的分析 prompt"""
    now = datetime.now(timezone(timedelta(hours=8)))
    today = now.strftime("%Y-%m-%d")

    lines = [
        f"今天是 {today}，以下是持有的基金今日净值数据：",
        "",
        "| 基金名称 | 代码 | 单位净值 | 日涨跌幅 |",
        "|---------|------|---------|:-------:|",
    ]

    for fund in cfg.funds:
        code = fund["code"]
        name = fund["name"]
        point = results.get(code)
        if point:
            lines.append(
                f"| {name} | {code} | {point.net_value:.4f} | {point.daily_change:+.2f}% |"
            )
        else:
            lines.append(f"| {name} | {code} | — | 无数据 |")

    lines.append("")

    # 用户自定义 prompt
    if cfg.ai_prompt:
        lines.append(cfg.ai_prompt)
    else:
        lines.append(
            "请根据以上数据给出简短分析：\n"
            "1. 今日整体表现如何？\n"
            "2. 值得关注的涨跌\n"
            "3. 短期趋势判断"
        )

    return "\n".join(lines)
