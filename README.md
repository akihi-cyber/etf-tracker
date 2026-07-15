# 📊 ETF Tracker — 基金净值日报自动追踪

> 每天收盘后自动爬取你持有的基金净值数据，交叉验证后生成日报并发送到 Outlook 邮箱。

---

## 🚀 快速开始

### 1.  Fork / Clone 后配置 Secrets

在你的 GitHub 仓库中，进入 **Settings → Secrets and variables → Actions → New repository secret**，添加：

| Secret 名称 | 值 |
|------------|-----|
| `OUTLOOK_EMAIL` | 你的 Outlook 邮箱地址 |
| `OUTLOOK_PASSWORD` | Outlook 密码（如果开启了两步验证，需要使用 **应用密码**） |
| `AI_API_KEY` | （可选）如果启用 AI 分析，放你的 API Key |

> 如何获取 Outlook 应用密码：  
> 登录 https://account.microsoft.com/security → 高级安全选项 → 应用密码

### 2. （可选）修改基金列表

编辑 `config/settings.yaml`，按格式添加/移除基金。  
**commit & push 后自动生效**，无需修改任何代码。

### 3. 触发运行

- **自动**：每个工作日北京时间 20:00 自动运行
- **手动**：在 GitHub 仓库的 Actions 页 → 点 "ETF 日报追踪" → **Run workflow**

---

## 📋 完整文件结构

```
etf-tracker/
├── .github/workflows/
│   └── daily-track.yml       ← GitHub Actions 定时器配置
├── config/
│   └── settings.yaml         ← ★ 你只需要改这个文件
├── src/
│   ├── main.py               ← 主入口
│   ├── config.py             ← 配置解析
│   ├── fetchers/
│   │   ├── eastmoney_fund.py ← ① 东方财富基金净值 API（主力）
│   │   ├── fallback.py       ← ② 新浪 API + 页面抓取（兜底）
│   │   └── base.py           ← 数据模型定义
│   ├── validator.py          ← 交叉验证 + 重试
│   ├── analyzer.py           ← AI 分析（占位，可选启用）
│   ├── reporter.py           ← 日报生成（Markdown）
│   └── mailer.py             ← Outlook SMTP 发送
├── data/                     ← 历史日报存档
├── requirements.txt          ← 依赖（只有 requests + PyYAML）
├── .env.example              ← 本地测试配置模板
└── README.md
```

---

## 🛡️ 稳定性设计

### 多层数据获取

```
东方财富基金API（主） → 新浪基金API（备1） → 天天基金页面抓取（备2）
```

每一层都有最多 **3 次自动重试**（10 秒间隔）。  
主源 API 已稳定运行 5 年以上，变动概率极低。

### 交叉验证

- 多个数据源之间对比净值，偏差 <0.5% 才可信
- 自动过滤异常涨跌幅（超过 ±15% 视为无效数据）
- 任何源失败不影响其他基金数据获取

### 失败处理

- 数据获取失败 → 自动重试 → 切兜底
- 邮件发送失败 → 日报仍保留在仓库的 `data/` 目录下
- 所有错误信息会包含在日报末尾

---

## ⚙️ 配置说明（config/settings.yaml）

```yaml
schedule:
  time: "20:00"        # 运行时间（北京时间）
  timezone: "Asia/Shanghai"

funds:
  - code: "001917"     # 基金代码
    name: "招商量化精选股票A"  # 显示名称
    type: fund         # fund=基金净值 / etf=盘中行情

validation:
  min_sources: 2       # 最少需要几个源一致
  max_retries: 3       # 每个源最多重试次数

ai_analysis:
  enabled: false       # 设为 true 启用 AI 分析
```

---

## 🧪 本地测试

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量（复制 .env.example）
cp .env.example .env
# 编辑 .env 填入你的 Outlook 凭据

# 3. 运行
python src/main.py
```

---

## 📮 输出示例

日报通过 Outlook 邮件发送，包含：

- **净值一览表**（基金名、代码、净值、涨跌幅、数据源）
- **组合概况**（平均涨跌、净值总和）
- **各基金明细**（单位净值、累计净值、日涨跌幅）
- **AI 分析**（可选，预留接口）
- **数据异常说明**（如有）

---

## 📡 RSS 订阅

每次生成日报后会同步更新 `data/feed.xml`。如果只使用 GitHub raw 地址，响应头通常是 `text/plain`，部分严格的 RSS 阅读器可能无法识别。

推荐部署 Web 服务后订阅：

```text
https://你的域名/feed.xml
```

本地检查：

```bash
uvicorn src.web:app --reload --port 8080
```

然后打开 `http://127.0.0.1:8080/feed.xml`。该接口会显式返回 `application/rss+xml`。

---

## 🤖 后续可扩展

- [ ] AI 分析接入 DeepSeek/OpenAI
- [ ] Telegram/微信通知
- [ ] 净值走势图（周/月 K 线）
- [ ] 组合收益率计算（基于初始投入）
- [ ] 自定义调仓提醒阈值

---

## 📝 License

MIT
