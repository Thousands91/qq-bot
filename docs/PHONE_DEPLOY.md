# 📱 手机部署完全指南（免费方案）

> 全程只用手机浏览器 + 手机 QQ，不需要电脑、不需要信用卡、不需要花钱。

---

## 方案对比：选哪个？

| 方案 | 费用 | 稳定性 | 手机操作难度 | 推荐度 |
|---|---|---|---|---|
| **GitHub Codespaces** | 免费 60 小时/月 | ⭐⭐⭐ 会休眠 | ⭐⭐⭐⭐⭐ 最简单 | ⭐⭐⭐⭐ |
| **Oracle Cloud 永久免费** | 永久免费 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ 需信用卡 | ⭐⭐⭐⭐⭐ |
| Termux（手机本地跑） | 免费 | ⭐ 极易掉线 | ⭐⭐ 很麻烦 | ⭐ |

**先试 Codespaces**，跑通后再考虑 Oracle。

---

# 方案 A：GitHub Codespaces（推荐新手）

## 你要准备什么

- 一个 GitHub 账号（免费注册）
- 手机 QQ（装好，已登录你的**小号**）
- 手机浏览器（Chrome / Safari 都行）

## 第 1 步：把项目传到 GitHub

1. 手机浏览器打开 https://github.com/new
2. **Repository name** 填 `qq-bot`，选 **Private**，点 `Create repository`
3. 进入新仓库，点 **Add file → Upload files**
4. 点 `choose your files`，把项目里的**所有文件**选上上传

> 手机上不方便选整个文件夹？更简单的方法在下面「方法 B」。

### 方法 B：用 GitHub 网页直接建文件（更稳）

如果上传文件夹麻烦，下载我给你的 `qq-bot-project.zip`，然后：

1. 电脑上解压 → 上传（借一下别人的电脑最快）
2. 或者直接用 **GitHub Codespaces 自己建文件**

**其实还有更简单的路**：直接 fork 别人现成的、配置好的仓库，然后改配置。搜索 GitHub 关键词 `nonebot go-cqhttp template`。

---

## 第 2 步：打开 Codespaces

1. 在仓库页面点绿色的 **Code** 按钮
2. 切到 **Codespaces** 标签
3. 点 **Create codespace on main**
4. 等 1-2 分钟，会出现一个**网页版 VS Code**

> 手机上 VS Code 界面有点挤，但能用。建议横屏。

---

## 第 3 步：配置 .env

1. 左侧文件树找到 `bot/.env.example`
2. 点开它，全选复制
3. 新建文件 `bot/.env`（右键 bot 文件夹 → New File）
4. 粘贴，然后修改这几项：

```env
SUPERUSERS=["你的QQ号"]
BOT_QQ=机器人QQ号
OPENAI_API_KEY=你的Key
OPENAI_BASE_URL=https://api.siliconflow.cn/v1
OPENAI_MODEL=Qwen/Qwen2.5-7B-Instruct
```

5. `Ctrl+S` 保存（手机上点右上角 ☰ → Save）

### 怎么免费拿 AI Key（3 分钟）

1. 手机浏览器打开 https://cloud.siliconflow.cn
2. 手机号注册（**注册即送 14 元额度**，够跑很久）
3. 左侧「API 密钥」→ 新建 → 复制
4. 粘到 `.env` 的 `OPENAI_API_KEY`

也可以换成 **DeepSeek**（10 元可以用很久）：https://platform.deepseek.com

---

## 第 4 步：打开终端，启动机器人

1. 在 Codespace 里按 `Ctrl + ` ` （反引号），或者点顶部菜单 → **Terminal → New Terminal**
2. 粘贴这一行，回车：

```bash
bash scripts/run.sh
```

3. 等 1-2 分钟，它会自动：
   - 装依赖
   - 下载 go-cqhttp
   - 启动机器人

---

## 第 5 步：扫码登录（关键！）

启动后终端会显示一大片黑白方块，那是**二维码**。

**手机操作**：

1. **把 Codespace 终端的二维码截图**（手机截图）
2. 打开手机 QQ → 右上角 **+** → **扫一扫**
3. 点右下角 **相册**，选刚才那张截图
4. 确认登录

> ⚠️ **手机上难点**：二维码在你手机上显示，但扫码也要用手机。
>
> **解决办法**：
> - 用第二台手机扫码
> - 或者：在 Codespace 里点 `cqhttp/data/qrcode.png`，用**电脑/平板**打开扫
> - 或者：长按二维码图片 → 保存 → 用 QQ 扫一扫从相册选

**登录成功标志**：终端出现 `登录成功` 或 `账号信息` 字样。

---

## 第 6 步：测试

1. 打开 QQ，找到你的小号，**拉进一个群**（自己建个测试群）
2. 群里发：`/抽签`
3. 机器人应该立刻回复

**如果没反应**，看第 7 步排错。

---

## 第 7 步：排错

在 Codespace 终端运行：

```bash
bash scripts/status.sh
```

会显示两个进程状态和最近的日志。

### 常见问题

| 现象 | 原因 | 解决 |
|---|---|---|
| 终端没有二维码 | 下载失败 | 手动下载 go-cqhttp 传到 `cqhttp/` 目录 |
| 扫码后提示「账号异常」 | 风控 | 换号，或等 24 小时 |
| 机器人不回复 | 没连上 | 看 `bot.log`，检查 `.env` 里 `SUPERUSERS` |
| `ModuleNotFoundError` | 依赖没装好 | 重跑 `bash scripts/run.sh` |
| 报错 `412` | 需要签名服务 | 换 go-cqhttp 版本，或看下文的签名方案 |

---

## 第 8 步：让 Codespace 不掉线

Codespaces **30 分钟无操作会自动停**，免费额度 60 小时/月。

**保持在线的方法**：

1. 让 Codespace 标签页一直开着（手机别关浏览器）
2. 或者在 Codespace 里跑一个保活脚本：

```bash
while true; do echo "keep alive"; sleep 300; done
```

> 但 Codespaces 本身有 4 小时强制休眠限制，**做不到 7×24**。
> 想 7×24 → 用方案 B（Oracle）。

---

# 方案 B：Oracle Cloud 永久免费（7×24 推荐）

## 成本

- **永久免费**：1 核 1G 内存云主机 + 200G 流量/月
- 需要**信用卡验证**（扣 1 美元预授权，会退）

## 步骤

### 1. 注册

手机浏览器打开 https://www.oracle.com/cloud/free/

- 国家选 **中国**
- 需要邮箱 + 手机号 + 信用卡
- ⚠️ **注册容易被拒**（中国区尤其），多试几次或换邮箱

### 2. 创建实例

登录后 → **Compute → Instances → Create Instance**

| 选项 | 选什么 |
|---|---|
| Image | **Ubuntu 22.04** |
| Shape | **VM.Standard.E2.1.Micro**（免费） |
| Boot volume | 默认 47GB |
| SSH key | **下载保存私钥**（重要！） |

点 **Create**，等 2 分钟，记下**公网 IP**。

### 3. 用手机 SSH 登录

下载 App：**Termius**（iOS/Android 都有，免费版够用）

新建 Host：
- Address：你的公网 IP
- Username：`ubuntu`
- Key：导入刚才下载的私钥

连接。

### 4. 装环境 + 跑起来

连上后，粘贴这一整段（一次性）：

```bash
# 装 Python 和 git
sudo apt update && sudo apt install -y python3 python3-pip python3-venv git unzip curl

# 把项目传上来（用 GitHub 或 scp）
# 如果项目已传到 GitHub：
git clone https://github.com/你的用户名/qq-bot.git
cd qq-bot

# 一键启动
bash scripts/run.sh
```

### 5. 保持后台运行（关掉 Termius 也不掉线）

```bash
sudo apt install -y screen
screen -S qqbot
bash scripts/run.sh
# 按 Ctrl+A 再按 D 脱离
```

### 6. 重启后自动拉起

```bash
sudo tee /etc/systemd/system/qqbot.service << 'EOF'
[Unit]
Description=QQ Bot
After=network.target

[Service]
Type=forking
User=ubuntu
WorkingDirectory=/home/ubuntu/qq-bot
ExecStart=/bin/bash /home/ubuntu/qq-bot/scripts/run-daemon.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable qqbot
sudo systemctl start qqbot
```

---

# 🔴 必读：小号安全须知

用 go-cqhttp 有封号风险。降低风险的方法：

1. ✅ **用小号**，不要用主号
2. ✅ 小号**实名认证 + 绑定手机号**
3. ✅ 小号手动发几条消息，看起来像真人
4. ✅ **关闭设备锁**（不然会一直掉线）
5. ❌ 不要频繁加群、群发广告（秒封）
6. ❌ 不要用刚注册的号（最容易封）
7. ❌ 不要同一 IP 跑多个机器人

**如果被封了**：
- 手机 QQ 会提示「账号被冻结」
- 去 https://aq.qq.com 申诉
- 一般 24-72 小时解封
- **换一个 device.json 再跑**（在 `cqhttp/data/` 里删掉）

---

# 📋 命令速查

在 Codespace / Termius 里用：

```bash
bash scripts/run.sh       # 启动
bash scripts/stop.sh      # 停止
bash scripts/restart.sh   # 重启
bash scripts/status.sh    # 看状态
bash scripts/qrcode.sh    # 重新显示二维码

tail -f bot.log           # 实时看机器人日志
tail -f cqhttp/cqhttp.log # 实时看 go-cqhttp 日志
```

---

# 💬 群里的命令

| 命令 | 功能 |
|---|---|
| `@机器人 你好` | AI 智能回复 |
| `/抽签` | 今日运势 |
| `/天气 北京` | 查天气 |
| `看图` / `看景` | 随机二次元图 / 真人摄影 |
| `早上好` / `菜单` | 关键词自动回复 |
| `/清空记忆` | 重置 AI 对话上下文 |


---

# ❓ 还是搞不定？

把这两样发给我：

1. `bash scripts/status.sh` 的输出
2. `tail -50 bot.log` 的输出

我帮你看哪里卡住了。
