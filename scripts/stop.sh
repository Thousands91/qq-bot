#!/usr/bin/env bash
# 停止机器人
set -e
cd "$(dirname "$0")/.."

echo "正在停止..."
pkill -f "go-cqhttp" 2>/dev/null && echo "✓ go-cqhttp 已停止" || echo "- go-cqhttp 未运行"
pkill -f "python main.py" 2>/dev/null && echo "✓ NoneBot 已停止" || echo "- NoneBot 未运行"
echo "完成"
