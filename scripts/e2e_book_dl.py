"""端到端：/找书 下载古籍，看机器人是否真的发出 file 段"""
import asyncio
import base64
import json
import os
import sys

import aiohttp

PORT = 8095
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
                        for seg in msg:
                            t = seg.get("type")
                            data = seg.get("data") or {}
                            if t == "text":
                                txt = data.get("text", "")
                                if txt.strip():
                                    print(f"   ← [text] {txt.strip()[:110]}")
                            elif t == "file":
                                raw = data.get("file", "")
                                size = len(base64.b64decode(
                                    raw.replace("base64://", ""))) \
                                    if raw.startswith("base64://") else len(raw)
                                print(f"   ← [file] 名称={data.get('name')} "
                                      f"大小={size // 1024}KB")
                    if d.get("echo"):
                        await ws.send_json({"status": "ok", "retcode": 0,
                                            "data": {"message_id": 1},
                                            "echo": d["echo"]})

            t = asyncio.create_task(reader())
            await asyncio.sleep(1)

            for text, wait in [("/找书 三字经", 4), ("/找书 三字经 下载", 15),
                               ("/找书 山海经 下载", 25),
                               ("/找书 三体 下载", 6)]:
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
                await asyncio.sleep(wait)

            await asyncio.sleep(3)
            t.cancel()

    proc.terminate()
    await asyncio.sleep(1)
    pt.cancel()


asyncio.run(main())
