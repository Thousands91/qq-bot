#!/usr/bin/env bash
# 查看运行状态
set -e
cd "$(dirname "$0")/.."

echo "======================================"
echo "  运行状态"
echo "======================================"

if pgrep -f "go-cqhttp" > /dev/null; then
  echo "go-cqhttp : 🟢 运行中 (PID $(pgrep -f 'go-cqhttp' | head -1))"
else
  echo "go-cqhttp : 🔴 未运行"
fi

if pgrep -f "python main.py" > /dev/null; then
  echo "NoneBot   : 🟢 运行中 (PID $(pgrep -f 'python main.py' | head -1))"
else
  echo "NoneBot   : 🔴 未运行"
fi

echo ""
echo "最近 10 行 go-cqhttp 日志："
echo "--------------------------------------"
tail -10 cqhttp/cqhttp.log 2>/dev/null || echo "(无日志)"
echo ""
echo "最近 10 行机器人日志："
echo "--------------------------------------"
tail -10 bot.log 2>/dev/null || echo "(无日志)"
