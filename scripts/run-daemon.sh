#!/usr/bin/env bash
# 守护模式启动（配合 systemd 使用）
set -e
cd "$(dirname "$0")/.."
ROOT=$(pwd)

# 清理旧进程
pkill -f "go-cqhttp" 2>/dev/null || true
sleep 1

# 启动 go-cqhttp
cd cqhttp
if [ ! -f config.yml ]; then
  cp ../docker/go-cqhttp/config.yml config.yml
fi
nohup ./go-cqhttp -faststart > cqhttp.log 2>&1 &
sleep 6
cd "$ROOT"

# 启动 bot
source bot/.venv/bin/activate
cd bot
nohup python main.py > ../bot.log 2>&1 &
