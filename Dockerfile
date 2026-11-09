# 阿萨尔云端镜像 —— ClawCloud Run 部署用
# 构建：GitHub Actions 自动构建推送到 ghcr.io/thousands91/asar-bot
FROM python:3.11-slim

WORKDIR /app

# 先装依赖（利用层缓存）
COPY bot/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 拷代码（.env/core dump/测试已被 .dockerignore 排除）
COPY bot/ /app/

# 记忆等运行时数据放 data/，首次启动从 data_seed 播种（挂卷后卷会盖住原路径）
RUN cp -r /app/data /app/data_seed 2>/dev/null || mkdir -p /app/data_seed
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV HOST=0.0.0.0
ENV PORT=8099
EXPOSE 8099

ENTRYPOINT ["/entrypoint.sh"]
