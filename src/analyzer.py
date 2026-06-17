"""
AI 分析模块（占位）

当前禁用，可通过 settings.yaml 启用。
启用时需要配置 AI_API_KEY 环境变量。
"""

from .config import Config
from .fetchers.base import FundDataPoint


def analyze(cfg: Config, results: dict[str, FundDataPoint]) -> str | None:
    """调用 AI 进行简短分析。占位用，直接返回 None"""
    if not cfg.ai_enabled:
        return None

    if not cfg.ai_api_key:
        return "⚠️ AI 分析已启用但未配置 API Key"

    # ─── 这里是预留的 AI 分析接口 ───
    # 需要实现时：
    # 1. 根据 cfg.ai_provider 选择 API
    # 2. 构造 prompt（包含当日净值数据和 cfg.ai_prompt）
    # 3. 调用 API 拿到回复
    # 4. 返回分析文本
    #
    # 示例（DeepSeek API）：
    #   headers = {"Authorization": f"Bearer {cfg.ai_api_key}"}
    #   payload = {
    #       "model": "deepseek-chat",
    #       "messages": [{"role": "user", "content": prompt}]
    #   }
    #   resp = requests.post("https://api.deepseek.com/chat/completions",
    #                        json=payload, headers=headers, timeout=30)
    #   return resp.json()["choices"][0]["message"]["content"]

    return "🤖 AI 分析功能将在后续版本开启"
