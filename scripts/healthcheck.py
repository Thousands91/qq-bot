"""体检：不靠猜，把每个可疑点实际跑一遍

关注点都是"用户敲了会出问题"的路径：
1. 空前缀后，裸词命令与 keyword_reply 抢话
2. 天气 / 点歌 去掉前缀的写法
3. 抽签的"所长 == 所短"
4. AI 对话的截断与上下文
5. 菜单里写的命令是否真的存在
"""
import asyncio
import json
import os
import sys

import aiohttp

PORT = 8111
BOT_UIN = 3111111111
GROUP = 999888777
USER = 555444333


async def main():
    env = dict(os.environ)
    env["PORT"] = str(PORT)
    env["ONEBOT_ACCESS_TOKEN"] = "test"
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "main.py", cwd="bot", env=env,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
    )
    logs = []

    async def pump():
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            logs.append(line.decode("utf-8", "ignore").rstrip())

    pt = asyncio.create_task(pump())
    await asyncio.sleep(7)

    url = f"ws://127.0.0.1:{PORT}/onebot/v11/ws"
    headers = {"X-Self-ID": str(BOT_UIN), "X-Client-Role": "Universal",
               "Authorization": "Bearer test"}
    got = {"text": ""}

    async with aiohttp.ClientSession() as sess:
        async with sess.ws_connect(url, headers=headers, max_msg_size=0) as ws:
            async def reader():
                async for m in ws:
                    if m.type != aiohttp.WSMsgType.TEXT:
                        continue
                    d = json.loads(m.data)
                    params = d.get("params") or {}
                    msg = params.get("message")
                    if isinstance(msg, list):
                        has_img = any(x.get("type") == "image" for x in msg)
                        t = "".join((x.get("data") or {}).get("text", "")
                                    for x in msg if x.get("type") == "text")
                        if t.strip() or has_img:
                            got["text"] += (t.strip() + " " if t.strip() else "") + \
                                           ("[图片]" if has_img else "")
                    if d.get("echo"):
                        await ws.send_json({"status": "ok", "retcode": 0,
                                            "data": {"message_id": 1},
                                            "echo": d["echo"]})

            rt = asyncio.create_task(reader())
            await asyncio.sleep(1)

            async def ask(text, at_me=False, wait=6):
                got["text"] = ""
                segs = []
                if at_me:
                    segs.append({"type": "at", "data": {"qq": "3111111111"}})
                segs.append({"type": "text", "data": {"text": " " + text if at_me else text}})
                ev = {
                    "time": 1700000000, "self_id": BOT_UIN,
                    "post_type": "message", "message_type": "group",
                    "sub_type": "normal", "message_id": 3001,
                    "group_id": GROUP, "user_id": USER, "anonymous": None,
                    "message": segs, "raw_message": text, "font": 0,
                    "sender": {"user_id": USER, "nickname": "体检员",
                               "card": "", "role": "member"},
                }
                await ws.send_json(ev)
                await asyncio.sleep(wait)
                return got["text"].strip()

            cases = [
                # (标签, 消息, 是否@, 期望说明)
                ("菜单", "菜单", False, "列出命令"),
                ("裸词找书", "找书", False, "应提示报书名"),
                ("裸词天气", "天气", False, "应提示说地名"),
                ("裸词天气带城市", "天气 北京", False, "应给北京天气"),
                ("斜杠天气带城市", "/天气 北京", False, "前缀应被削掉"),
                ("裸词看图", "看图", False, "应发图"),
                ("裸词抽签", "抽签", False, "应出签"),
                ("裸词新闻", "新闻", False, "应出十件大事"),
                ("裸词点歌", "点歌", False, "应提示说歌名"),
                ("@问吃什么", "今天吃什么", True, "AI 应答"),
            ]
            for label, text, at, note in cases:
                r = await ask(text, at_me=at, wait=8 if "点歌" in label or "看图" in label else 6)
                one = r.replace("\n", " / ")[:90]
                print(f"[{label}] {text!r}\n    → {one or '（无回复）'}\n    期望：{note}")

            rt.cancel()

    proc.terminate()
    await asyncio.sleep(1)
    pt.cancel()

    print("\n===== 可疑日志 =====")
    for l in logs:
        if any(k in l for k in ("ERROR", "Traceback", "WARNING", "Exception")):
            print(l[:200])


asyncio.run(main())
