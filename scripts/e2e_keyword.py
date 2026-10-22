"""端到端：起真服务 + 假 OneBot 客户端，验证关键词触发与误触

重点不是"能不能回"，而是"该沉默的时候会不会多嘴"。
"""
import asyncio
import json
import os
import sys

import aiohttp

PORT = 8097
BOT_UIN = 3000000000

# (消息, 期望里有回复 / 期望沉默)
CASES = [
    ("早上好", True),
    ("早安", True),            # 同义词
    ("这本书不错", False),      # 原来会误触"书"
    ("今天早上好冷啊", False),   # 原来会误触"早上好"
    ("群主", True),
    ("苏丹卡", True),
    ("菜单", True),
    ("今晚吃什么呢", False),
    ("/找书 三国演义", True),   # 走找书命令，不是关键词
]


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
            if any(k in s for k in ("ERROR", "Traceback", "keyword_reply")):
                print("  [bot]", s)

    pt = asyncio.create_task(pump())
    await asyncio.sleep(6)

    url = f"ws://127.0.0.1:{PORT}/onebot/v11/ws"
    headers = {"X-Self-ID": str(BOT_UIN), "X-Client-Role": "Universal",
               "Authorization": "Bearer test"}
    got = {"text": ""}

    async with aiohttp.ClientSession() as sess:
        async with sess.ws_connect(url, headers=headers, max_msg_size=0) as ws:
            print("✅ WS 连上\n")

            async def reader():
                async for m in ws:
                    if m.type != aiohttp.WSMsgType.TEXT:
                        continue
                    d = json.loads(m.data)
                    params = d.get("params") or {}
                    msg = params.get("message")
                    if isinstance(msg, list):
                        t = "".join((x.get("data") or {}).get("text", "")
                                    for x in msg if x.get("type") == "text")
                        if t.strip():
                            got["text"] += t.strip() + " | "
                    if d.get("echo"):
                        await ws.send_json({"status": "ok", "retcode": 0,
                                            "data": {"message_id": 1},
                                            "echo": d["echo"]})

            rt = asyncio.create_task(reader())
            await asyncio.sleep(1)

            bad = 0
            for text, expect in CASES:
                got["text"] = ""
                ev = {
                    "time": 1700000000, "self_id": BOT_UIN,
                    "post_type": "message", "message_type": "group",
                    "sub_type": "normal", "message_id": 2001,
                    "group_id": 123456789, "user_id": 987654321,
                    "anonymous": None,
                    "message": [{"type": "text", "data": {"text": text}}],
                    "raw_message": text, "font": 0,
                    "sender": {"user_id": 987654321, "nickname": "测试员",
                               "card": "", "role": "member"},
                }
                await ws.send_json(ev)
                await asyncio.sleep(3)
                said = bool(got["text"].strip())
                ok = (said == expect)
                if not ok:
                    bad += 1
                mark = "✓" if ok else "✗"
                print(f"{mark} {text:<18} 期望{'回复' if expect else '沉默'}  "
                      f"实际{'回复' if said else '沉默'}  {got['text'][:56]}")

            rt.cancel()
            print(f"\n{len(CASES)-bad}/{len(CASES)} 通过")

    proc.terminate()
    await asyncio.sleep(1)
    pt.cancel()
    sys.exit(1 if bad else 0)


asyncio.run(main())
