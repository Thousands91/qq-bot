# 详细部署 / 风控 / 常见问题

## 一、为什么强烈建议用小号

go-cqhttp 是基于 QQ 协议的**逆向实现**，腾讯官方不认可。

- 2023-2025 期间，已有多次大规模封号（按地区、按号段）
- 主号被封后**申诉极难恢复**
- 风控对**新注册 / 短期未登录**的号尤为严格

**安全建议**：

1. 使用**至少 5 年以上**的 QQ 小号
2. 小号需**实名认证 + 绑手机 + 关设备锁**
3. 在小号上**手动发出几条消息**，看起来像个真人用号
4. 关闭**空间 / 相册 / 邮箱**等所有第三方网页登录

---

## 二、风控具体表现 + 解封思路

### 常见错误码

| 错误日志 | 含义 | 应对 |
|---|---|---|
| `账号在另一地点登录, 被踢下线` | TX 检测到协议不一致 | 退出后用手机端登录一次再重新扫码 |
| `账号被冻结, 请登录 QQ 安全中心解除` | 风控已拦截 | 去 [aq.qq.com](https://aq.qq.com) 申诉或解封，**等几个小时再跑** |
| `当前 QQ 版本太低, 请更新到最新版本` | 协议版本模拟问题 | 升级 go-cqhttp 到最新 release |
| `发送消息过于频繁, 请稍后再试` | 速率限制 | 降低消息频率，避免刷屏 |

### 解封思路

1. 立刻停掉 go-cqhttp
2. 用**手机 QQ** 登录看是否正常
3. 收到 TX 短信的话，按短信提示走申诉
4. **24 小时后再试**，不复用同一份 device.json

---

## 三、Docker 安装速查

### Windows / Mac

装 [Docker Desktop](https://www.docker.com/products/docker-desktop/)。

### Linux (Ubuntu/Debian)

```bash
curl -fsSL https://get.docker.com | bash
sudo usermod -aG docker $USER   # 避免每次 sudo
# 然后重新登录
```

### 验证

```bash
docker --version
docker compose version
```

---

## 四、不用 Docker 直接跑（开发用）

```bash
cd bot
python3.11 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 还需要另起一个 go-cqhttp 进程：
# 1. 下载 https://github.com/Mrs4s/go-cqhttp/releases
# 2. 用 docker/go-cqhttp/config.yml
# 3. 双击/命令行启动 go-cqhttp

# 等 go-cqhttp 就绪后：
cp .env.example .env  # 编辑
python main.py
```

---

## 五、功能扩展

### 加一个新插件

```bash
# 在 bot/plugins/ 下加一个 my_plugin.py
cd bot/plugins
touch my_plugin.py
```

最少骨架：

```python
from nonebot import on_command
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message

my_cmd = on_command("你好", priority=20, block=True)

@my_cmd.handle()
async def _(event: GroupMessageEvent):
    await my_cmd.finish(Message("世界你好！"))
```

重启 bot 即可生效（`docker compose restart bot`）。

### 接入不同大模型

只要是 OpenAI 兼容协议，改 `OPENAI_BASE_URL` 即可：

| 服务 | Base URL | 推荐模型 |
|---|---|---|
| 硅基流动 | `https://api.siliconflow.cn/v1` | Qwen2.5-7B-Instruct |
| DeepSeek | `https://api.deepseek.com/v1` | deepseek-chat |
| 智谱 | `https://open.bigmodel.cn/api/paas/v4` | glm-4-flash |
| 字节豆包 | `https://ark.cn-beijing.volces.com/api/v3` | doubao-lite-32k |
| 月之暗面 | `https://api.moonshot.cn/v1` | moonshot-v1-8k |

如果某个平台不是 100% 兼容 openai sdk，把 `ai_chat.py` 的 `call_llm` 替换为它的 SDK 调用即可。

### 修改关键词回复

直接编辑 `bot/plugins/keyword_reply.py` 的对应常量，保存后：

```bash
docker compose restart bot
```

---

## 六、进阶：使用 MySQL / SQLite 持久化

当前 AI 对话、关键词统计都是放在内存，重启会丢。需要持久化可加：

```bash
pip install sqlalchemy[asyncio] databases[sqlite]
```

然后参考 [NoneBot 文档 - 数据存储](https://nonebot.dev/docs/advanced/database)。

---

## 七、常见问题清单

**Q：扫码提示 "操作过于频繁"**
A：换 IP。换设备（手机 4G/宽带路由）。隔天再试。

**Q：机器人不响应消息**
A：
1. 确认 Bot 收到的不是全 `https://sign.xxxx` 类的加密消息——可能需要部署自己的签名服务
2. 看日志 `docker compose logs -f bot` 有没有报错
3. 检查 `.env` 的 `SUPERUSERS` 是否填了你的 QQ

**Q：发不出去图片**
A：go-cqhttp 默认 protocol 41。新版可以用 `pro://xxxxxx` 这种格式：
   - 在 docker/go-cqhttp/config.yml 加 `protocol: 41`

**Q：机器人一启动就被踢下线**
A：风控。换号或等待 24 小时。

**Q：能不能用官方 QQ 机器人？**
A：可以，但功能受限（不能主动发消息、不能读聊天记录）。如果只是自动回复，可以试试 [QQ 开放平台](https://q.qq.com)。

**Q：能不能做付费/私域用？**
A：技术上能。但**触红线（仿冒官方、做营销扩散）会加速封号**。建议用 SaaS 工具如「腾讯小微」「微伴」等合规方案。

---

## 八、合规提示

QQ 用户协议明确禁止使用第三方客户端。go-cqhttp 的存在基于**逆向协议**这一灰产地带。任何商业化运营都建议走 QQ 官方开放平台。
