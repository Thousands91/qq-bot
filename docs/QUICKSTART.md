# 5 分钟上手教程 🚀

按本文操作，**最快 5 分钟就能让机器人加入你的 QQ 群**。

## 1. 准备账号与环境

- 一个**小号 QQ**（强烈建议，跟主号隔离）
- 已下载并安装 [Docker Desktop](https://www.docker.com/products/docker-desktop/) 或 Linux 上的 docker + docker-compose
- 一个 AI 大模型 API Key（推荐 [硅基流动](https://cloud.siliconflow.cn/i/ykXtJqAR)，注册就送免费额度，足够个人用很久）

## 2. 克隆 / 解压项目

把项目放在任意目录，例如 `~/qq-bot-project`，目录结构长这样：

```
qq-bot-project/
├── bot/         ← NoneBot 代码
├── docker/      ← docker-compose 和 go-cqhttp 配置
└── docs/        ← 文档
```

## 3. 填写配置

进入 `bot` 目录，复制配置模板并编辑：

```bash
cd bot
cp .env.example .env
notepad .env     # Windows
# 或 vim .env    # Linux/macOS
```

**最少必须填这两项**：

| 变量 | 说明 |
|---|---|
| `OPENAI_API_KEY` | 你的大模型 API Key |
| `OPENAI_BASE_URL` | 比如 `https://api.siliconflow.cn/v1` |

其它都先用默认值即可。

## 4. 一键启动

```bash
cd ../docker
docker compose up -d --build
```

启动完成后两个容器都应该是 `running` 状态。

## 5. 扫码登录 QQ

第一次启动 go-cqhttp 需要扫码：

```bash
docker compose logs -f go-cqhttp
```

你会看到日志里有一个链接，例如：`https://accounts.qq.com/...`，或者一个二维码图片链接。
- 用**小号**的扫码工具登录
- 扫码后等待几秒，机器人就上线了

## 6. 把机器人拉进群

1. 在 QQ 里创建一个普通群（你已经是群主就行）
2. 用**小号**邀请**主号**（你现在的号）进群
3. 用小号同意后，再让**主号**邀请**小号机器人**进群
4. 在群里输入 `菜单`，看机器人有没有回复

### 试一下：

- `菜单` - 看功能列表
- `/抽签` - 测今日运势
- `/天气 北京` - 查天气
- `@机器人 你叫什么名字` - AI 对话

## 7. 关闭 / 重启

```bash
docker compose stop       # 停
docker compose start      # 起
docker compose down       # 删容器（数据保留在 volume）
docker compose down -v    # 删容器 + 数据 ⚠️
```

## 8. 实时看日志

```bash
docker compose logs -f          # 全部
docker compose logs -f bot      # 只看 Bot
docker compose logs -f go-cqhttp  # 只看 go-cqhttp
```

---

**完事！** 到这里你应该能看到机器人回复了。如果遇到问题，下一步看 [DEPLOYMENT.md](./DEPLOYMENT.md) 排查。
