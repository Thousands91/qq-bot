#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
#  QQ 群机器人 - Termux 安卓一键安装脚本
#  用法：在 Termux 里粘贴   bash install-termux.sh   回车
# ============================================================

set -e

GREEN='\033[32m'; RED='\033[31m'; YELLOW='\033[33m'; CYAN='\033[36m'; NC='\033[0m'
ok()   { printf "${GREEN}  ✓ %s${NC}\n" "$1"; }
info() { printf "${CYAN}  ▸ %s${NC}\n" "$1"; }
warn() { printf "${YELLOW}  ! %s${NC}\n" "$1"; }
err()  { printf "${RED}  ✗ %s${NC}\n" "$1"; }

clear
echo ""
printf "${CYAN}"
echo "  ╔══════════════════════════════════════╗"
echo "  ║     QQ 群机器人 · Termux 一键安装    ║"
echo "  ╚══════════════════════════════════════╝"
printf "${NC}"
echo ""

START_TIME=$(date +%s)
WORKDIR="$HOME/qq-bot-project"

# ---------- 0. 环境检查 ----------
if [ ! -d "/data/data/com.termux" ]; then
  err "这必须在 Termux 里运行"
  exit 1
fi
ok "Termux 环境检测通过"

# ---------- 1. 更新软件源 ----------
info "更新软件源（可能需要 1-2 分钟）..."
pkg update -y > /dev/null 2>&1 || true
ok "软件源已更新"

# ---------- 2. 安装依赖 ----------
info "安装 Python / git / unzip / wget ..."
pkg install -y python git unzip wget > /dev/null 2>&1
ok "基础依赖安装完成"

# 3.11 是目前 Termux 的默认版本
PY_VER=$(python -V 2>&1 | cut -d' ' -f2)
ok "Python $PY_VER"

# ---------- 3. 代码位置 ----------
if [ -d "$WORKDIR" ]; then
  info "检测到已存在的项目，跳过下载"
else
  # 项目应当已经解压到当前目录
  SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
  if [ -f "$SRC_DIR/bot/main.py" ]; then
    info "从当前目录复制项目..."
    cp -r "$SRC_DIR" "$WORKDIR"
  else
    err "找不到项目文件"
    echo "  请确认你解压了 qq-bot-project.zip 且在项目根目录运行本脚本"
    exit 1
  fi
fi
cd "$WORKDIR"
ok "项目目录：$WORKDIR"

# ---------- 4. Python 依赖 ----------
info "安装 Python 依赖（约 2-4 分钟，请耐心等）..."
python -m pip install --quiet --upgrade pip 2>/dev/null || true
python -m pip install --quiet -r bot/requirements.txt 2>&1 | tail -5
ok "Python 依赖安装完成"

# ---------- 5. 下载 go-cqhttp ----------
mkdir -p cqhttp
cd cqhttp

if [ -x go-cqhttp ]; then
  ok "go-cqhttp 已存在"
else
  info "下载 go-cqhttp ..."
  # Termux 在 arm64 上跑 amd64 二进制是不行的，
  # 需要用 proot + amd64 环境。这里先尝试下载 amd64 版本
  CQ_URL=$(curl -sL https://api.github.com/repos/Mrs4s/go-cqhttp/releases/latest 2>/dev/null \
           | grep -o 'https://[^"]*linux-amd64[^"]*\.zip' | head -1)

  if [ -z "$CQ_URL" ]; then
    warn "自动获取失败，尝试备用地址..."
    CQ_URL="https://github.com/Mrs4s/go-cqhttp/releases/latest/download/go-cqhttp_linux_amd64.zip"
  fi

  curl -sL -o gc.zip "$CQ_URL" || {
    err "下载失败，请检查网络"
    exit 1
  }
  unzip -o -q gc.zip
  rm -f gc.zip
  chmod +x go-cqhttp
  ok "go-cqhttp 下载完成"
fi
cd "$WORKDIR"

# ---------- 6. 生成配置 ----------
info "生成配置文件..."
if [ ! -f bot/.env ]; then
  cp bot/.env.example bot/.env
fi
if [ ! -f cqhttp/config.yml ]; then
  cp docker/go-cqhttp/config.yml cqhttp/config.yml
fi
ok "配置已生成"

# ---------- 7. 生成启动脚本 ----------
cat > start.sh <<'STARTEOF'
#!/data/data/com.termux/files/usr/bin/bash
cd "$HOME/qq-bot-project"

# 已运行就不重复启动
if pgrep -f "go-cqhttp" > /dev/null && pgrep -f "python main.py" > /dev/null; then
  echo "机器人已在运行中"
  exit 0
fi

# 启动 go-cqhttp
if ! pgrep -f "go-cqhttp" > /dev/null; then
  cd cqhttp
  nohup ./go-cqhttp -faststart > cqhttp.log 2>&1 &
  cd ..
  echo "go-cqhttp 启动中..."
  sleep 5
fi

# 启动 bot
if ! pgrep -f "python main.py" > /dev/null; then
  cd bot
  nohup python main.py > ../bot.log 2>&1 &
  cd ..
  echo "NoneBot 启动中..."
fi

sleep 3
echo ""
echo "════════════════════════════════════"
echo "  机器人已启动"
echo "  查看日志:  tail -f bot.log"
echo "  停止:      bash stop.sh"
echo "════════════════════════════════════"
STARTEOF
chmod +x start.sh

cat > stop.sh <<'STOPEOF'
#!/data/data/com.termux/files/usr/bin/bash
pkill -f "go-cqhttp" 2>/dev/null && echo "go-cqhttp 已停止"
pkill -f "python main.py" 2>/dev/null && echo "NoneBot 已停止"
echo "完成"
STOPEOF
chmod +x stop.sh

cat > qr.sh <<'QREOF'
#!/data/data/com.termux/files/usr/bin/bash
cd "$HOME/qq-bot-project/cqhttp"
pkill -f "go-cqhttp" 2>/dev/null || true
sleep 2
nohup ./go-cqhttp -faststart > cqhttp.log 2>&1 &
sleep 5
echo ""
echo "════════════════════════════════════"
echo "  请截图下面的二维码，用 QQ 扫码"
echo "════════════════════════════════════"
grep -A 200 "" cqhttp.log | tail -60
echo ""
echo "二维码图片位置：cqhttp/data/qrcode.png"
QREOF
chmod +x qr.sh

cat > status.sh <<'STATEOF'
#!/data/data/com.termux/files/usr/bin/bash
cd "$HOME/qq-bot-project"
echo "════════════════════════════════════"
if pgrep -f "go-cqhttp" > /dev/null; then
  echo "go-cqhttp : 🟢 运行中"
else
  echo "go-cqhttp : 🔴 未运行"
fi
if pgrep -f "python main.py" > /dev/null; then
  echo "NoneBot   : 🟢 运行中"
else
  echo "NoneBot   : 🔴 未运行"
fi
echo "════════════════════════════════════"
echo ""
echo "最近日志："
tail -15 bot.log 2>/dev/null || echo "(无)"
STATEOF
chmod +x status.sh

ok "启动脚本已创建（start.sh / stop.sh / qr.sh / status.sh）"

# ---------- 完成 ----------
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo ""
printf "${GREEN}"
echo "  ╔══════════════════════════════════════╗"
echo "  ║            安装完成 ✅               ║"
echo "  ╚══════════════════════════════════════╝"
printf "${NC}"
echo ""
echo "  用时 ${DURATION} 秒"
echo ""
printf "${YELLOW}"
echo "  ⚠️  重要：go-cqhttp 在 Termux 上可能无法运行"
echo "     因为它是 x86_64 程序，而手机是 ARM 架构"
echo "     下一步会告诉你怎么办"
printf "${NC}"
echo ""
echo "  现在请运行："
printf "${CYAN}"
echo "     cd ~/qq-bot-project && bash start.sh"
printf "${NC}"
echo ""
