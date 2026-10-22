# 🏠 回广州开机手册（预计 5 分钟）

> 前提：电脑浏览器打开 https://github.com/codespaces → 点进 `opulent capybara` 那个 Codespace
> （如果提示 Stopped/已停止，点它启动等 1~2 分钟即可，代码和环境都在）

---

## 第 1 步：清掉密码登录（重要！不然又走滑块死路）

在终端粘贴：

```bash
sed -i 's/password: "你的密码"/password: ""/' /workspaces/qq-bot/cqhttp/config.yml && pkill go-cqhttp; echo CLEANED
```

出现 `CLEANED` 即可。

## 第 2 步：启动 go-cqhttp 并显示二维码

```bash
cd /workspaces/qq-bot/cqhttp && nohup ./go-cqhttp -faststart > cqhttp.log 2>&1 & sleep 10 && ls data/ && echo QR-READY
```

## 第 3 步：电脑上显示二维码（两种方式任选）

- **方式 A**：左侧文件树 → `cqhttp` → `data` → 点开 `qrcode.png`（电脑上直接显示）
- **方式 B**：如果 data 里没有，看 `cqhttp/cqhttp.log` 底部（终端会打印字符版二维码）

## 第 4 步：手机扫码（10 秒）

手机 QQ（**登录小号的那个**）→ 右上角 ＋ → **扫一扫** → 摄像头**对准电脑屏幕** → 确认登录

> 这次是实时摄像头扫屏幕，完全符合腾讯规则，之前手机上的一切障碍都不存在。

## 第 5 步：确认登录成功

```bash
tail -6 /workspaces/qq-bot/cqhttp/cqhttp.log
```

看到 **"登录成功"** 即上线 ✅

## 第 6 步：启动机器人（AI 对话等插件）

```bash
cd /workspaces/qq-bot/bot && nohup python main.py > ../bot.log 2>&1 & sleep 5 && tail -12 ../bot.log
```

看到 `[SUCCESS]` / 无报错即全部完成。

## 第 7 步：测试 🎉

把小号拉进你的 QQ 群，发：

- `/抽签` → 今日运势
- `@机器人 你好` → AI 回复（需先配置 AI Key，见下）
- `/天气 北京` → 天气
- 群里有人进群 → 自动欢迎

---

## 补充：配置 AI 问答（可选，2 分钟）

1. 手机/电脑浏览器打开 https://cloud.siliconflow.cn → 手机号注册（送 14 元额度）
2. 「API 密钥」→ 新建 → 复制 `sk-...`
3. Codespace 终端：

```bash
sed -i 's|OPENAI_API_KEY=|OPENAI_API_KEY=粘贴你的sk密钥|' /workspaces/qq-bot/bot/.env && pkill -f "python main.py"; cd /workspaces/qq-bot/bot && nohup python main.py > ../bot.log 2>&1 &
```

之后群里 @机器人 就有 AI 回复。

---

## 常见问题

| 问题 | 处理 |
|---|---|
| 扫码后提示"账号异常" | 风控，等 24 小时再试；或换号 |
| 登录成功但发消息没反应 | 看 `tail -20 bot.log`；确认 bot 进程在跑（`ps aux \| grep main.py`）|
| 发消息报 45 错误 | 需要签名服务器，回来后找我加配置 |
| Codespace 打不开 | 刷新；检查 https://github.com/codespaces 状态是否 Running |

## 保活提醒

Codespace 闲置 14 天会被删除（代码在 GitHub 仓库不丢，但环境需重建）。期间每隔几天打开一次 github.com/codespaces 点进去再退出即可。
