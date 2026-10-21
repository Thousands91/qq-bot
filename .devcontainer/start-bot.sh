#!/usr/bin/env bash
# Codespaces 每次启动时自动拉起机器人
set -e

cd "$(dirname "$0")/.."
ROOT=$(pwd)

# 后台跑 go-cqhttp（首次会要求扫码）
if [ -x cqhttp/go-cqhttp ]; then
  cd cqhttp
  if ! pgrep -f "go-cqhttp" > /dev/null; then
    nohup ./go-cqhttp -faststart > cqhttp.log 2>&1 &
    echo "go-cqhttp 已后台启动，日志：cqhttp/cqhttp.log"
  fi
  cd "$ROOT"
fi

# 后台跑 NoneBot
cd bot
if ! pgrep -f "python main.py" > /dev/null; then
  nohup python main.py > ../bot.log 2>&1 &
  echo "NoneBot 已后台启动，日志：bot.log"
fi
