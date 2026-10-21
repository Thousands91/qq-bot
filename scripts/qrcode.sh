#!/usr/bin/env bash
# 重新显示登录二维码（扫码过期后用）
set -e
cd "$(dirname "$0")/../cqhttp"

echo "正在重启 go-cqhttp 以显示新二维码..."
pkill -f "go-cqhttp" 2>/dev/null || true
sleep 2
nohup ./go-cqhttp -faststart > cqhttp.log 2>&1 &
sleep 4

echo ""
echo "======================================"
echo "  请用手机 QQ 扫描下方二维码"
echo "  手机 QQ -> 右上角 + -> 扫一扫"
echo "======================================"
echo ""
grep -A 200 "二维码" cqhttp.log 2>/dev/null | head -60 || tail -60 cqhttp.log

echo ""
echo "如果二维码显示错乱，请打开 cqhttp/data/qrcode.png 查看"
