#!/usr/bin/env bash
# Codespaces 首次创建时执行：装依赖 + 下载 go-cqhttp + 生成配置
set -e

cd "$(dirname "$0")/.."
ROOT=$(pwd)

echo "==> 1/4 安装 Python 依赖"
pip install --quiet --disable-pip-version-check -r bot/requirements.txt

echo "==> 2/4 准备 .env"
if [ ! -f bot/.env ]; then
  cp bot/.env.example bot/.env
  echo "    已从 .env.example 生成 bot/.env"
fi

echo "==> 3/4 下载 go-cqhttp"
mkdir -p cqhttp
cd cqhttp
if [ ! -f go-cqhttp ]; then
  # 取最新 release 的 linux amd64 压缩包
  URL=$(curl -sL https://api.github.com/repos/Mrs4s/go-cqhttp/releases/latest \
        | grep -o 'https://[^"]*linux-amd64[^"]*\.zip' | head -1)
  if [ -z "$URL" ]; then
    echo "    !! 自动获取下载地址失败，请手动下载："
    echo "    https://github.com/Mrs4s/go-cqhttp/releases"
  else
    echo "    下载 $URL"
    curl -sL -o gc.zip "$URL"
    unzip -o -q gc.zip
    rm -f gc.zip
    chmod +x go-cqhttp
  fi
fi
cd "$ROOT"

echo "==> 4/4 写入 go-cqhttp 配置"
mkdir -p cqhttp/data
cat > cqhttp/config.yml <<'YAML'
account:
  uin: 0
  password: ""
  encrypt: false
  status: 0
  relogin:
    delay: 3
    interval: 3
    max-times: 0

message:
  post-format: array
  ignore-invalid-cqcode: false
  force-fragment: false
  fix-url: false
  proxy-rewrite: ""
  report-self-message: false
  remove-reply-at: false
  extra-reply-data: false
  skip-mime-scan: false
  convert-webp-image: false

output:
  log-level: info
  log-aging: 15
  log-force-new: true
  debug: false

default-middlewares: &default
  access-token: ""
  filter: ""
  rate-limit:
    enabled: false
    frequency: 1
    bucket: 1
  cache:
    image: 0
    video: 0
    record: 0
    file: 0

database:
  leveldb:
    enable: true

heartbeat:
  interval: 5

http:
  enabled: false
  host: 0.0.0.0
  port: 5700
  timeout: 5
  middlewares:
    <<: *default

websocket:
  enabled: false
  host: 0.0.0.0
  port: 6700
  middlewares:
    <<: *default

reverse-ws:
  enabled: true
  universal: ws://127.0.0.1:8080/onebot/v11/ws
  api: ""
  event: ""
  reconnect-interval: 3000
  middlewares:
    <<: *default

servers:
  - http:
      host: 0.0.0.0
      port: 5700
      timeout: 5
    ws:
      host: 0.0.0.0
      port: 6700
YAML

echo ""
echo "======================================================"
echo " 初始化完成！"
echo " 下一步：运行  bash scripts/run.sh"
echo "======================================================"
