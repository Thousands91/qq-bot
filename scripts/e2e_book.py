"""端到端：起真服务 + 假 OneBot 客户端，发 /找书 看机器人回什么"""
import asyncio
import json
import os
import sys

import aiohttp

PORT = 8096
BOT_UIN = 3000000000


async def main():
    env = dict(os.environ)
    env["PORT"] = str(PORT)
    env["ONEBOT_ACCESS_TOKEN"] = "test"
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
            if any(k in s for k in ("ERROR", "Loaded adapters", "Traceback",
                                    "book_find", "Error")):
                print("  [bot]", s)

    pt = asyncio.create_task(pump())
    await asyncio.sleep(6)

    url = f"ws://127.0.0.1:{PORT}/onebot/v11/ws"
    headers = {"X-Self-ID": str(BOT_UIN), "X-Client-Role": "Universal",
               "Authorization": "Bearer test"}
    async with aiohttp.ClientSession() as sess:
        async with sess.ws_connect(url, headers=headers, max_msg_size=0) as ws:
            print("✅ WS 连上")

            async def reader():
                async for m in ws:
                    if m.type != aiohttp.WSMsgType.TEXT:
                        continue
                    d = json.loads(m.data)
                    params = d.get("params") or {}
                    msg = params.get("message")
                    if isinstance(msg, list):
                        txt = "".join((x.get("data") or {}).get("text", "")
                                      for x in msg if x.get("type") == "text")
                        if txt.strip():
                            print("   ← 机器人：")
                            for ln in txt.splitlines():
                                print("      ", ln)
                    if d.get("echo"):
                        await ws.send_json({"status": "ok", "retcode": 0,
                                            "data": {"message_id": 1},
                                            "echo": d["echo"]})

            t = asyncio.create_task(reader())
            await asyncio.sleep(1)

            for text in ["/找书 三体", "/找书 余华", "/找书 一本根本不存在的书"]:
                ev = {
                    "time": 1700000000, "self_id": BOT_UIN,
                    "post_type": "message", "message_type": "group",
                    "sub_type": "normal", "message_id": 1001,
                    "group_id": 123456789, "user_id": 987654321,
                    "anonymous": None,
                    "message": [{"type": "text", "data": {"text": text}}],
                    "raw_message": text, "font": 0,
                    "sender": {"user_id": 987654321, "nickname": "测试员",
                               "card": "", "role": "member"},
                }
                print(f"\n→ {text}")
                await ws.send_json(ev)
                await asyncio.sleep(3)

            await asyncio.sleep(2)
            t.cancel()

    proc.terminate()
    await asyncio.sleep(1)
    pt.cancel()


asyncio.run(main())
