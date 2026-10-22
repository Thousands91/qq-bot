#!/usr/bin/env bash
# ================================================
# 一键启动脚本（手机 / 任何 Linux 都能用）
# 用法：bash scripts/run.sh
# ================================================
set -e

cd "$(dirname "$0")/.."
ROOT=$(pwd)

green() { printf "\033[32m%s\033[0m\n" "$1"; }
red()   { printf "\033[31m%s\033[0m\n" "$1"; }
yellow(){ printf "\033[33m%s\033[0m\n" "$1"; }

echo "=============================================="
echo "        QQ 群机器人 一键启动"
echo "=============================================="
echo ""

# ---------- 检查 Python ----------
if ! command -v python3 > /dev/null 2>&1; then
  red "未找到 python3，请先安装 Python 3.10+"
  exit 1
fi
green "✓ Python $(python3 -V 2>&1 | cut -d' ' -f2)"

# ---------- 检查 .env ----------
if [ ! -f bot/.env ]; then
  yellow "! 未发现 bot/.env，正在从模板生成..."
  cp bot/.env.example bot/.env
  yellow "! 请先编辑 bot/.env 填入 API Key 等信息"
fi

# ---------- 安装依赖 ----------
if [ ! -d bot/.venv ]; then
  yellow "> 首次运行，正在创建虚拟环境..."
  python3 -m venv bot/.venv
fi
# shellcheck disable=SC1091
source bot/.venv/bin/activate

if ! python -c "import nonebot" 2>/dev/null; then
  yellow "> 正在安装依赖（首次约 1-2 分钟）..."
  pip install --quiet --disable-pip-version-check -r bot/requirements.txt
fi
green "✓ 依赖就绪"

# ---------- 检查 go-cqhttp ----------
if [ ! -x cqhttp/go-cqhttp ]; then
  yellow "! 未发现 go-cqhttp，正在自动下载..."
  mkdir -p cqhttp
  cd cqhttp
  URL=$(curl -sL https://api.github.com/repos/Mrs4s/go-cqhttp/releases/latest \
        | grep -o 'https://[^"]*linux-amd64[^"]*\.zip' | head -1)
  if [ -z "$URL" ]; then
    red "自动下载失败，请手动下载："
    echo "  https://github.com/Mrs4s/go-cqhttp/releases"
    echo "  解压后把 go-cqhttp 放到项目根目录的 cqhttp/ 下"
    exit 1
  fi
  curl -sL -o gc.zip "$URL"
  unzip -o -q gc.zip
  rm -f gc.zip
  chmod +x go-cqhttp
  cd "$ROOT"

  # 生成配置文件
  cp docker/go-cqhttp/config.yml cqhttp/config.yml 2>/dev/null || true
fi
green "✓ go-cqhttp 就绪"

# ---------- 启动 ----------
echo ""
echo "----------------------------------------------"
echo "  即将启动 go-cqhttp（首次需要扫码登录）"
echo "  扫码位置：终端里会出现二维码"
echo "  手机 QQ -> 右上角 + -> 扫一扫"
echo "----------------------------------------------"
echo ""

mkdir -p cqhttp/data
cd cqhttp

# 后台启动 go-cqhttp
nohup ./go-cqhttp -faststart > cqhttp.log 2>&1 &
CQ_PID=$!
echo "go-cqhttp 已启动 (PID $CQ_PID)"
echo "日志文件: cqhttp/cqhttp.log"
echo ""
echo "实时日志（Ctrl+C 只退出查看，不会停机器人）："
sleep 3
tail -f cqhttp.log &
TAIL_PID=$!

# 等 8 秒后启动 bot
sleep 8
cd "$ROOT/bot"
nohup python main.py > ../bot.log 2>&1 &
BOT_PID=$!
echo ""
green "NoneBot 已启动 (PID $BOT_PID)"
echo "日志文件: bot.log"
echo ""

sleep 3
cat ../bot.log 2>/dev/null | tail -20

echo ""
echo "=============================================="
green "  ✅ 启动完成！"
echo "=============================================="
echo ""
echo " 查看 go-cqhttp 日志:  tail -f cqhttp/cqhttp.log"
echo " 查看机器人日志:        tail -f bot.log"
echo " 停止全部:              bash scripts/stop.sh"
echo " 重启:                  bash scripts/restart.sh"
echo ""
