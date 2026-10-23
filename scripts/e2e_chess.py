"""端到端：国际象棋插件（对棋 / 走 / 棋局 / 认输 / 悔棋 / 结束棋局）"""
import asyncio
import json
import os
import sys

import aiohttp

PORT = 8096
BOT_UIN = 3000000000
GROUP = 123456789
A = 987654321   # 白方
B = 111222333   # 黑方


def group_msg(user_id: int, segs: list) -> dict:
    return {
        "time": 1700000000, "self_id": BOT_UIN,
        "post_type": "message", "message_type": "group",
        "sub_type": "normal", "message_id": 3001,
        "group_id": GROUP, "user_id": user_id,
        "anonymous": None, "message": segs,
        "raw_message": "".join(s["data"].get("text", "") for s in segs),
        "font": 0,
        "sender": {"user_id": user_id, "nickname": "t", "card": "", "role": "member"},
    }


async def main():
    env = dict(os.environ)
    env["PORT"] = str(PORT)
    env["ONEBOT_ACCESS_TOKEN"] = "test"
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "main.py", cwd="bot", env=env,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
    )

    botlog = open("/tmp/chess_bot.log", "w")

    async def pump():
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            s = line.decode("utf-8", "ignore").rstrip()
            botlog.write(s + "\n"); botlog.flush()
            if any(k in s for k in ("ERROR", "Traceback", "chess_game")):
                print("  [bot]", s)

    pt = asyncio.create_task(pump())
    await asyncio.sleep(6)

    url = f"ws://127.0.0.1:{PORT}/onebot/v11/ws"
    headers = {"X-Self-ID": str(BOT_UIN), "X-Client-Role": "Universal",
               "Authorization": "Bearer test"}
    got = {"segs": []}

    async with aiohttp.ClientSession() as sess:
        async with sess.ws_connect(url, headers=headers, max_msg_size=0) as ws:
            async def reader():
                async for m in ws:
                    if m.type != aiohttp.WSMsgType.TEXT:
                        continue
                    d = json.loads(m.data)
                    msg = (d.get("params") or {}).get("message")
                    if isinstance(msg, list):
                        got["segs"].append(msg)
                    if d.get("echo"):
                        await ws.send_json({"status": "ok", "retcode": 0,
                                            "data": {"message_id": 1},
                                            "echo": d["echo"]})

            rt = asyncio.create_task(reader())
            await asyncio.sleep(1)

            bad = 0

            async def step(name, user_id, segs, expect_img, expect_kw=None):
                got["segs"].clear()
                await ws.send_json(group_msg(user_id, segs))
                await asyncio.sleep(2.5)
                reply = got["segs"]
                if not reply:
                    print(f"✗ {name}: 沉默"); return 1
                text = "".join((s.get("data") or {}).get("text", "")
                               for msg in reply for s in msg if s.get("type") == "text")
                imgs = sum(1 for msg in reply for s in msg if s.get("type") == "image")
                ok = True
                if expect_img and imgs == 0:
                    ok = False
                if expect_kw and expect_kw not in text:
                    ok = False
                mark = "✓" if ok else "✗"
                if not ok:
                    nonlocal bad; bad += 1
                print(f"{mark} {name}: {text[:70]}  [图片x{imgs}]")
                return 0

            T = lambda t: [{"type": "text", "data": {"text": t}}]

            await step("对棋(未@,等待黑方)", A, T("对棋"), False, "下一位说话的人执黑")
            await step("走 e5(黑方认领)", B, T("走 e5"), False, "您执黑")
            await step("走 e4(白方)", A, T("走 e4"), True, "黑方")
            await step("走 e5(黑方)", B, T("走 e5"), True, "白方")
            await step("走 Nf3(白方)", A, T("走 Nf3"), True, "")
            await step("走 Nc6(黑方)", B, T("走 Nc6"), True, "")
            await step("棋局(看盘)", A, T("棋局"), True, "")
            await step("走 e2e4(UCI,非法占位)", A, T("走 e2e4"), False, "走不通")
            await step("走 Bb5", A, T("走 Bb5"), True, "")
            await step("悔棋(黑方)", B, T("悔棋"), True, "悔了一步")
            await step("重走 Bb5", A, T("走 Bb5"), True, "")
            await step("走 a6", B, T("走 a6"), True, "")
            await step("结束棋局(路人)", 999, T("结束棋局"), False, "别人的")
            await step("结束棋局(白方)", A, T("结束棋局"), False, "棋收了")

            # 快速将死流程
            await step("对棋@(开局)", A,
                       T("对棋") + [{"type": "at", "data": {"qq": str(B)}}],
                       False, "执黑")
            await step("走 f3", A, T("走 f3"), True, "")
            await step("走 e5", B, T("走 e5"), True, "")
            await step("走 g4", A, T("走 g4"), True, "")
            await step("走 Qh4#(将死)", B, T("走 Qh4#"), True, "将死")

            rt.cancel()
            print(f"\n{'✅ 全部通过' if bad == 0 else f'❌ {bad} 项失败'}")

    proc.terminate()
    await asyncio.sleep(1)
    pt.cancel()
    sys.exit(1 if bad else 0)


asyncio.run(main())
