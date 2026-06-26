# ============================================
# ETF Tracker — Dockerfile
# 最小化镜像，仅用于运行每日追踪脚本
# ============================================

FROM python:3.11-slim

LABEL description="ETF Tracker — 基金净值追踪 & 日报系统"
LABEL maintainer="Testiphi"

WORKDIR /app

# 安装依赖（利用 Docker 缓存层）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && rm -rf /root/.cache/pip

# 复制项目代码（排除 data/ 数据卷）
COPY src/ src/
COPY config/ config/
COPY requirements.txt .

# 数据持久化目录（SQLite + 日报）
VOLUME /app/data

# 默认以 UTC 运行，Python 代码内部按北京时间处理
ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Shanghai

CMD ["python", "src/main.py"]
