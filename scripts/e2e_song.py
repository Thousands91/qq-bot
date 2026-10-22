"""端到端：起真服务 + 假 OneBot 客户端，发一条 /点歌 看机器人回什么"""
import asyncio
import json
import os
import sys

import aiohttp

PORT = 8099
BOT_UIN = 3000000000
GROUP = 123456789
BASE = f"http://127.0.0.1:{PORT}"


async def ws_client(msgs):
    """连上反向 WS，把收到的 action 全记下来"""
    url = f"ws://127.0.0.1:{PORT}/onebot/v11/ws"
    headers = {"X-Self-ID": str(BOT_UIN), "X-Client-Role": "Universal",
               "Authorization": "Bearer test"}
    seen = []
    async with aiohttp.ClientSession() as sess:
        async with sess.ws_connect(url, headers=headers) as ws:
            print(f"✅ WS 连上 {url}")

            async def reader():
                async for m in ws:
                    if m.type == aiohttp.WSMsgType.TEXT:
                        d = json.loads(m.data)
                        seen.append(d)
                        act = d.get("action")
                        if act in ("send_msg", "send_group_msg"):
                            params = d.get("params") or {}
                            msg = params.get("message")
                            kind = "文本"
                            if isinstance(msg, list):
                                kinds = [x.get("type") for x in msg]
                                kind = "+".join(kinds)
                                text = "".join(
                                    (x.get("data") or {}).get("text", "")
                                    for x in msg if x.get("type") == "text"
                                )
                            else:
                                text = str(msg)
                            print(f"   ← 机器人发消息 [{kind}] {text[:120]}")
                        if act and d.get("echo"):
                            await ws.send_json({"status": "ok", "retcode": 0,
                                                "data": {"message_id": 1}, "echo": d["echo"]})

            t = asyncio.create_task(reader())
            await asyncio.sleep(1.2)
            for text in msgs:
                ev = {
                    "time": 1700000000, "self_id": BOT_UIN,
                    "post_type": "message", "message_type": "group",
                    "sub_type": "normal", "message_id": 1001,
                    "group_id": GROUP, "user_id": 987654321,
                    "anonymous": None,
                    "message": [{"type": "text", "data": {"text": text}}],
                    "raw_message": text, "font": 0,
                    "sender": {"user_id": 987654321, "nickname": "测试员",
                               "card": "", "role": "member"},
                }
                print(f"→ 发送：{text}")
                await ws.send_json(ev)
                await asyncio.sleep(18)
            t.cancel()
    return seen


async def main():
    env = dict(os.environ)
    env["PORT"] = str(PORT)
    env["ONEBOT_ACCESS_TOKEN"] = "test"
    env["DRIVER"] = "~fastapi"
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "main.py", cwd="bot", env=env,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
    )

    async def pump():
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            s = line.decode("utf-8", "ignore").rstrip()
            if any(k in s for k in ("ERROR", "SUCCESS]", "Launched", "Uvicorn", "Running", "❌")):
                print("  [bot]", s)

    pt = asyncio.create_task(pump())
    await asyncio.sleep(6)
    try:
        await ws_client(["/点歌 两只老虎爱跳舞", "/点歌 晴天 周杰伦"])
    finally:
        proc.terminate()
        await asyncio.sleep(1)
        pt.cancel()


asyncio.run(main())
