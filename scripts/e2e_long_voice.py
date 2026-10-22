"""专项：验证长语音（>200 秒 / 10MB+）发出去到底会怎样。

模拟 NapCat 的慢速应答：收到 record 后等 N 秒再回 ok，看插件是成功、
还是超时退回卡片、还是崩。
"""
import asyncio
import json
import os
import sys

import aiohttp

PORT = 8097
BOT_UIN = 3000000000
BASE = f"http://127.0.0.1:{PORT}"
ACK_DELAY = 40  # 模拟 silk 转码 + 上传耗时


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
            if any(k in s for k in ("ERROR", "NetworkError", "Traceback",
                                    "song_request.py", "TimeoutError", "Cancelled")):
                print("  [bot]", s)

    pt = asyncio.create_task(pump())
    await asyncio.sleep(6)

    url = f"ws://127.0.0.1:{PORT}/onebot/v11/ws"
    headers = {"X-Self-ID": str(BOT_UIN), "X-Client-Role": "Universal",
               "Authorization": "Bearer test"}
    async with aiohttp.ClientSession() as sess:
        # max_msg_size=0：语音走 base64，十几兆的帧，默认 4MB 上限直接拒收
        async with sess.ws_connect(url, headers=headers, max_msg_size=0) as ws:
            print(f"✅ WS 连上（模拟 NapCat 应答延迟 {ACK_DELAY}s）")

            async def reader():
                async for m in ws:
                    if m.type != aiohttp.WSMsgType.TEXT:
                        continue
                    d = json.loads(m.data)
                    act = d.get("action")
                    params = d.get("params") or {}
                    msg = params.get("message")
                    if isinstance(msg, list):
                        kinds = "+".join(x.get("type") for x in msg)
                        txt = "".join((x.get("data") or {}).get("text", "")
                                      for x in msg if x.get("type") == "text")
                        # 语音段里塞的是 base64，打印出来有十几兆，会卡死循环
                        print(f"   ← [{kinds}] {txt[:100] or '(语音数据)'}")
                    if act and d.get("echo"):
                        if "record" in str(act) or (isinstance(msg, list) and
                                                    any(x.get("type") == "record" for x in msg)):
                            print(f"      (语音已发出，等 {ACK_DELAY}s 再回应答)")

                            async def later(e=d["echo"]):
                                await asyncio.sleep(ACK_DELAY)
                                try:
                                    await ws.send_json({"status": "ok", "retcode": 0,
                                                        "data": {"message_id": 1}, "echo": e})
                                    print("      (应答已回)")
                                except Exception:
                                    pass

                            asyncio.create_task(later())
                        else:
                            await ws.send_json({"status": "ok", "retcode": 0,
                                                "data": {"message_id": 1},
                                                "echo": d["echo"]})

            t = asyncio.create_task(reader())
            await asyncio.sleep(1)

            text = "/点歌 晴天 周杰伦"
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
            print(f"→ {text}")
            await ws.send_json(ev)

            await asyncio.sleep(120)
            t.cancel()

    proc.terminate()
    await asyncio.sleep(1)
    pt.cancel()


asyncio.run(main())
