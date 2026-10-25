import asyncio, json, os, sys, aiohttp
PORT = 8085
BOT_UIN = 3000000000

async def main():
    env = dict(os.environ)
    env["PORT"] = str(PORT)
    env["ONEBOT_ACCESS_TOKEN"] = "test"
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "main.py", cwd="bot", env=env,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
    await asyncio.sleep(6)
    bad = 0
    async with aiohttp.ClientSession() as sess:
        async with sess.ws_connect(
                f"ws://127.0.0.1:{PORT}/onebot/v11/ws",
                headers={"X-Self-ID": str(BOT_UIN), "X-Client-Role": "Universal",
                         "Authorization": "Bearer test"},
                max_msg_size=0) as ws:
            got = {"segs": []}

            async def rd():
                async for m in ws:
                    if m.type != aiohttp.WSMsgType.TEXT:
                        continue
                    d = json.loads(m.data)
                    msg = (d.get("params") or {}).get("message")
                    if isinstance(msg, list):
                        got["segs"].append(msg)
                    if d.get("echo"):
                        await ws.send_json({"status": "ok", "retcode": 0,
                                            "data": {}, "echo": d["echo"]})

            rt = asyncio.create_task(rd())
            await asyncio.sleep(1)

            async def probe(name, text, expect_reply, wait=8):
                nonlocal bad
                got["segs"].clear()
                await ws.send_json({
                    "time": 0, "self_id": BOT_UIN, "post_type": "message",
                    "message_type": "group", "sub_type": "normal",
                    "message_id": 1, "group_id": 123, "user_id": 987654321,
                    "anonymous": None,
                    "message": [{"type": "text", "data": {"text": text}}],
                    "raw_message": "", "font": 0,
                    "sender": {"user_id": 987654321, "nickname": "t",
                               "card": "", "role": "member"}})
                await asyncio.sleep(wait)
                replied = bool(got["segs"])
                ok = replied == expect_reply
                if not ok:
                    bad += 1
                t = "".join((s.get("data") or {}).get("text", "")
                            for msg in got["segs"]
                            for s in msg if s.get("type") == "text")[:40]
                print(("OK  " if ok else "FAIL ") + name + ": " +
                      (("回复: " + t) if replied else "沉默"))

            await probe("新闻（句首）", "新闻", True)
            await probe("今天有什么新闻（句中）", "今天有什么新闻", False)
            await probe("新闻联播（命令开头+多余字）", "新闻联播", True)
            await probe("早上好（关键词整句）", "早上好", True)
            await probe("今天早上好冷（关键词句中）", "今天早上好冷", False)
            await probe("早上好啊各位（关键词+语气尾巴）", "早上好啊各位", True)
            rt.cancel()
            print("ALL PASS" if bad == 0 else f"FAIL x{bad}")
    proc.terminate()
    await asyncio.sleep(1)
    sys.exit(1 if bad else 0)

asyncio.run(main())
