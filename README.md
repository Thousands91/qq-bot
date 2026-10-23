# QQ 群机器人（可直接在群中使用）

基于 **NoneBot v2 + go-cqhttp** 的开箱即用 QQ 群机器人。

> 📱 **手机上操作？直接看 [`docs/PHONE_DEPLOY.md`](docs/PHONE_DEPLOY.md)**  
> ⚡ 想快速跑起来？看 [`docs/QUICKSTART.md`](docs/QUICKSTART.md)

---

## 功能一览

| 功能 | 触发方式 | 说明 |
|---|---|---|
| 🤖 **AI 智能问答** | `@机器人 问题` | 支持上下文、多轮对话 |
| 💬 **关键词回复** | 发关键词 | 可在配置里自定义 |
| 🎴 **抽签 / 运势** | `/抽签` | 每天每人固定一签 |
| 🌤️ **天气查询** | `天气 北京` | Open-Meteo，免 key |
| 📰 **新闻早报** | `新闻` / `早报` | 每日十件大事 + 农历，免 key |
| 📖 **找书** | `/找书 三体` | 豆瓣书目 + 阿萨尔一句评 |
| 📜 **下古籍** | `/找书 山海经 下载` | 公有领域古籍，直接发 txt |
| 🎵 **点歌** | `/点歌 晴天` | 有音频发语音，否则发卡片 |
| 🖼️ **随机图片** | `看图` / `看景` | 二次元图（私聊可 R18）/ 真人摄影，均全年龄起 |
| 🧹 **清空记忆** | `/清空记忆` | 重置 AI 上下文 |

---

## 30 秒上手

```bash
cp bot/.env.example bot/.env   # 1. 复制配置
# 2. 编辑 bot/.env 填入 QQ 号和 API Key
bash scripts/run.sh            # 3. 一键启动
```

启动后终端会显示二维码，用**手机 QQ 扫码登录**即可。

其他命令：

```bash
bash scripts/status.sh    # 查看状态
bash scripts/stop.sh      # 停止
bash scripts/restart.sh   # 重启
bash scripts/qrcode.sh    # 重新显示二维码
```

---

## 目录结构

```
qq-bot-project/
├── bot/                        # NoneBot 主程序
│   ├── main.py                 # 启动入口
│   ├── config.py               # 配置加载
│   ├── requirements.txt        # 依赖
│   ├── .env.example            # 环境变量模板 → 复制为 .env
│   └── plugins/                # 功能插件（加文件即加功能）
│       ├── ai_chat.py          # AI 问答
│       ├── keyword_reply.py    # 关键词回复
│       ├── fortune.py          # 抽签
│       ├── weather.py          # 天气
│       ├── news.py             # 新闻早报
│       └── image_search.py     # 随机图
├── scripts/                    # 一键脚本
│   ├── run.sh                  # 启动（自动装依赖、下载 cqhttp）
│   ├── stop.sh                 # 停止
│   ├── restart.sh              # 重启
│   ├── status.sh               # 状态
│   ├── qrcode.sh               # 重扫码
│   └── run-daemon.sh           # systemd 守护模式
├── .devcontainer/              # GitHub Codespaces 自动配置
│   ├── devcontainer.json
│   ├── setup.sh
│   └── start-bot.sh
├── docker/                     # Docker 部署（可选）
│   ├── docker-compose.yml
│   ├── Dockerfile.bot
│   ├── Dockerfile.go-cqhttp
│   └── go-cqhttp/config.yml
└── docs/
    ├── PHONE_DEPLOY.md         # 📱 手机部署完整指南
    ├── QUICKSTART.md           # 5 分钟上手
    └── DEPLOYMENT.md           # 深入文档 / 风控 FAQ
```

---

## 部署方式任选

| 方式 | 适用场景 | 文档 |
|---|---|---|
| **GitHub Codespaces** | 免费、手机可操作、不需信用卡 | [PHONE_DEPLOY.md](docs/PHONE_DEPLOY.md) 方案 A |
| **Oracle Cloud 免费机** | 7×24 稳定、永久免费 | [PHONE_DEPLOY.md](docs/PHONE_DEPLOY.md) 方案 B |
| **本地电脑 / 服务器** | 调试开发 | [QUICKSTART.md](docs/QUICKSTART.md) |
| **Docker** | 有 Docker 的服务器 | `cd docker && docker compose up -d` |

---

## 免费 AI 配置

推荐 **硅基流动**（注册送 14 元，国内直连）：

1. https://cloud.siliconflow.cn 手机号注册
2. 左侧「API 密钥」→ 新建 → 复制
3. 填入 `bot/.env`：

```env
OPENAI_API_KEY=sk-xxxxxxxx
OPENAI_BASE_URL=https://api.siliconflow.cn/v1
OPENAI_MODEL=Qwen/Qwen2.5-7B-Instruct
```

也支持 DeepSeek / 智谱 / 豆包 / 月之暗面，改 `OPENAI_BASE_URL` 即可。

---

## 加功能

在 `bot/plugins/` 下新建 `.py` 文件，重启即生效：

```python
from nonebot import on_command
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message

hello = on_command("hello", priority=20, block=True)

@hello.handle()
async def _(event: GroupMessageEvent):
    await hello.finish(Message("Hi! 👋"))
```

---

## ⚠️ 风险提示

- go-cqhttp 基于**逆向协议**，有**封号风险**
- **务必用小号**，不要用主号
- 详见 [DEPLOYMENT.md](docs/DEPLOYMENT.md) 的「风控」章节

> QQ 用户协议禁止第三方客户端。商业用途请走 [QQ 开放平台](https://q.qq.com)。
