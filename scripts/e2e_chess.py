"""端到端：国际象棋插件（双人@接棋开局 / 走 /  认输 / 结束）"""
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
    env["CHESS_TIMEOUT"] = "30"  # 超时缩短到 30 秒，可测懒判负
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
                await asyncio.sleep(1.2)
                reply = got["segs"]
                if not reply:
                    if expect_kw is False and not expect_img:
                        print(f"✓ {name}: 沉默（符合预期）")
                    else:
                        print(f"✗ {name}: 沉默"); nonlocal bad; bad += 1
                    return
                text = "".join((s.get("data") or {}).get("text", "")
                               for msg in reply for s in msg if s.get("type") == "text")
                imgs = sum(1 for msg in reply for s in msg if s.get("type") == "image")
                ok = True
                if expect_img and imgs == 0:
                    ok = False
                if expect_kw and expect_kw not in text:
                    ok = False
                if expect_kw is False and text.strip():
                    ok = False
                mark = "✓" if ok else "✗"
                if not ok:
                    bad += 1
                print(f"{mark} {name}: {text[:70]}  [图片x{imgs}]")

            async def step_p(name, user_id, text, expect_kw):
                got["segs"].clear()
                await ws.send_json({
                    "time": 0, "self_id": BOT_UIN, "post_type": "message",
                    "message_type": "private", "sub_type": "friend",
                    "message_id": 4001, "user_id": user_id,
                    "message": [{"type": "text", "data": {"text": text}}],
                    "raw_message": text, "font": 0,
                    "sender": {"user_id": user_id, "nickname": "t"},
                })
                await asyncio.sleep(1.2)
                text_r = "".join((sg.get("data") or {}).get("text", "")
                                 for msg in got["segs"] for sg in msg if sg.get("type") == "text")
                ok = expect_kw in text_r
                mark = "✓" if ok else "✗"
                if not ok: nonlocal bad; bad += 1
                print(f"{mark} {name}: {text_r[:60]}")

            T = lambda t: [{"type": "text", "data": {"text": t}}]
            ATB = lambda: [{"type": "at", "data": {"qq": str(BOT_UIN)}}]
            START = lambda: ATB() + T("国际象棋")

            await step("裸「国际象棋」没@我", A, T("国际象棋"), False, False)
            await step("没棋局时说「走吧」", A, T("走吧"), False, False)
            await step("没棋局时说「走 e4」", A, ATB() + T("走 e4"), False, False)
            await step("没棋局时说「认输」", A, ATB() + T("认输"), False, False)
            await step("没棋局时说「结束棋局」", A, ATB() + T("结束棋局"), False, False)
            await step_p("私聊开局被拒", A, "国际象棋", "来群里")
            await step("A @我 开局(占白)", A, START(), False, "执白")
            await step("A 再报一次", A, START(), False, "黑棋得让别人来")
            await step("B @我 接黑(开局)", B, START(), True, "执白先行")
            await step("A 报第三次(已开局)", A, START(), False, "没空摆第二盘")
            await step("走 e4(白)", A, ATB() + T("走 e4"), True, "轮到黑方")
            await step("路人乱走", 999, ATB() + T("走 e5"), False, "轮到黑方走")
            await step("走 e5(黑)", B, ATB() + T("走 e5"), True, "轮到白方")
            await step("走 Nf3(白)", A, ATB() + T("走 Nf3"), True, "")
            await step("走 Nc6(黑)", B, ATB() + T("走 Nc6"), True, "")
            await step("走 e2e4(UCI非法)", A, ATB() + T("走 e2e4"), False, "走不通")
            await step("走 Bb5(白)", A, ATB() + T("走 Bb5"), True, "")
            await step("走 a6(黑)", B, ATB() + T("走 a6"), True, "")
            await step("结束棋局(路人)", 999, ATB() + T("结束棋局"), False, "别替人收")
            await step("结束棋局(白)", A, ATB() + T("结束棋局"), False, "棋收了")

            # 快速将死
            await step("再开局", A, START(), False, "执白")
            await step("B 接黑", B, START(), True, "执白先行")
            await step("走 f3", A, ATB() + T("走 f3"), True, "")
            await step("走 e5", B, ATB() + T("走 e5"), True, "")
            await step("走 g4", A, ATB() + T("走 g4"), True, "")
            await step("走 Qh4#(将死)", B, ATB() + T("走 Qh4#"), True, "将死")

            # ---- 补测：特殊走法与边界 ----
            await step("再开局(将死后)", A, START(), False, "执白")
            await step("C 接黑(第三人)", 555, START(), True, "执白先行")
            # 意大利开局 + 王车易位
            await step("e4", A, ATB() + T("走 e4"), True, "")
            await step("e5", 555, ATB() + T("走 e5"), True, "")
            await step("Nf3", A, ATB() + T("走 Nf3"), True, "")
            await step("Nc6", 555, ATB() + T("走 Nc6"), True, "")
            await step("Bc4", A, ATB() + T("走 Bc4"), True, "")
            await step("Bc5", 555, ATB() + T("走 Bc5"), True, "")
            await step("白方 O-O 易位", A, ATB() + T("走 O-O"), True, "")
            await step("黑方 Nf6", 555, ATB() + T("走 Nf6"), True, "")
            await step("白 h3", A, ATB() + T("走 h3"), True, "")
            await step("黑方 O-O 易位", 555, ATB() + T("走 O-O"), True, "")
            # 吃过路兵：d2d4 c7c5 d4d5 c5 想吃过路兵需要黑走 e7e5 后 dxe6
            await step("白 a4", A, ATB() + T("走 a4"), True, "")
            await step("黑 a6", 555, ATB() + T("走 a6"), True, "")
            await step("白 a5", A, ATB() + T("走 a5"), True, "")
            await step("黑 b5(冲双格)", 555, ATB() + T("走 b5"), True, "")
            await step("axb6 吃过路兵", A, ATB() + T("走 axb6"), True, "")
            # 认输：黑方认输
            await step("黑方认输", 555, ATB() + T("认输"), False, "投子认负")
            # 别名「不下了」
            await step("再开局", A, START(), False, "执白")
            await step("B 接黑", B, START(), True, "执白先行")
            await step("白方「不下了」", A, ATB() + T("不下了"), False, "棋收了")
            # 等待 9 秒触发懒判负：白方开局后不接黑，8 秒超时
            await step("开局后晾着", A, START(), False, "执白")
            await asyncio.sleep(35)
            await step("超时后走子触发清理", A, ATB() + T("走 e4"), False, "也没人来接棋")
            # 带标点开局
            await step("「国际象棋！」带标点", A, ATB() + T("国际象棋！"), False, "执白")
            await step("清场(收掉等待中的局)", A, ATB() + T("结束棋局"), False, "棋收了")

            rt.cancel()
            print(f"\n{'✅ 全部通过' if bad == 0 else f'❌ {bad} 项失败'}")

    proc.terminate()
    await asyncio.sleep(1)
    pt.cancel()
    sys.exit(1 if bad else 0)


asyncio.run(main())
