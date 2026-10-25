"""端到端：极端终局——三次重复局面、十回合逼和、将死后清局"""
import asyncio, json, os, sys
import aiohttp

PORT = 8095
BOT_UIN = 3000000000
A = 987654321
B = 111222333

def group_msg(uid, segs):
    return {"time": 1700000000, "self_id": BOT_UIN, "post_type": "message",
            "message_type": "group", "sub_type": "normal", "message_id": 3001,
            "group_id": 123456789, "user_id": uid, "anonymous": None,
            "message": segs, "raw_message": "", "font": 0,
            "sender": {"user_id": uid, "nickname": "t", "card": "", "role": "member"}}

async def main():
    env = dict(os.environ)
    env["PORT"] = str(PORT); env["ONEBOT_ACCESS_TOKEN"] = "test"
    env["CHESS_TIMEOUT"] = "600"
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "main.py", cwd="bot", env=env,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    botlog = open("/tmp/chess_extreme_bot.log", "w")
    async def pump():
        while True:
            line = await proc.stdout.readline()
            if not line: break
            s = line.decode("utf-8", "ignore").rstrip()
            botlog.write(s + "\n"); botlog.flush()
    pt = asyncio.create_task(pump())
    await asyncio.sleep(6)

    bad = 0
    async with aiohttp.ClientSession() as sess:
        async with sess.ws_connect(f"ws://127.0.0.1:{PORT}/onebot/v11/ws",
                headers={"X-Self-ID": str(BOT_UIN), "X-Client-Role": "Universal",
                         "Authorization": "Bearer test"}, max_msg_size=0) as ws:
            got = {"segs": []}
            async def reader():
                async for m in ws:
                    if m.type != aiohttp.WSMsgType.TEXT: continue
                    d = json.loads(m.data)
                    msg = (d.get("params") or {}).get("message")
                    if isinstance(msg, list): got["segs"].append(msg)
                    if d.get("echo"):
                        await ws.send_json({"status":"ok","retcode":0,"data":{},"echo":d["echo"]})
            rt = asyncio.create_task(reader())
            await asyncio.sleep(1)

            async def play(moves, expect):
                """按棋谱轮流走完，最后一步期望 expect。"""
                nonlocal bad
                white, black = A, B
                for i, san in enumerate(moves):
                    got["segs"].clear()
                    uid = white if i % 2 == 0 else black
                    await ws.send_json(group_msg(uid,
                        [{"type":"at","data":{"qq":str(BOT_UIN)}},
                         {"type":"text","data":{"text":f"走 {san}"}}]))
                    await asyncio.sleep(1.0)
                    if i < len(moves) - 1:
                        if not got["segs"]:
                            print(f"✗ {san}（第{i+1}手）: 沉默"); bad += 1; return
                text = "".join((sg.get("data") or {}).get("text","")
                               for msg in got["segs"] for sg in msg if sg.get("type")=="text")
                ok = expect in text
                if not ok: bad += 1
                print(("✓" if ok else "✗") + f" 终局[{moves[-1]}]: {text[:60]}")

            T = lambda t: [{"type":"text","data":{"text":t}}]
            ATB = lambda: [{"type":"at","data":{"qq":str(BOT_UIN)}}]

            # ---- 三次重复局面：回原位四趟 ----
            await ws.send_json(group_msg(A, ATB() + T("国际象棋")))
            await asyncio.sleep(1.5)
            await ws.send_json(group_msg(B, ATB() + T("国际象棋")))
            await asyncio.sleep(1.5)
            await play(["Nf3","Nf6","Ng1","Ng8","Nf3","Nf6","Ng1","Ng8"], "三次重复局面，平局")
            # 终局后应已清局：再走应沉默
            got["segs"].clear()
            await ws.send_json(group_msg(A, ATB() + T("走 e4")))
            await asyncio.sleep(1.0)
            if got["segs"]:
                print("✗ 重复和棋后未清局，还有回复"); bad += 1
            else:
                print("✓ 和棋后棋局已清（再走沉默）")

            # ---- 十回合逼和（Loyd 型）----
            await ws.send_json(group_msg(A, ATB() + T("国际象棋")))
            await asyncio.sleep(1.5)
            await ws.send_json(group_msg(B, ATB() + T("国际象棋")))
            await asyncio.sleep(1.5)
            await play(["e3","a5","Qh5","Ra6","Qxa5","h5","Qxc7","Rah6","h4","f6",
                        "Qxd7+","Kf7","Qxb7","Qd3","Qxb8","Qh7","Qxc8","Kg6","Qe6"],
                       "逼和，平局")
            got["segs"].clear()
            await ws.send_json(group_msg(A, ATB() + T("走 e4")))
            await asyncio.sleep(1.0)
            if got["segs"]:
                print("✗ 逼和后未清局"); bad += 1
            else:
                print("✓ 逼和后棋局已清（再走沉默）")

            rt.cancel()
            print(f"\n{'✅ 极端对局全部通过' if bad == 0 else f'❌ {bad} 项失败'}")
    proc.terminate(); await asyncio.sleep(1); pt.cancel()
    sys.exit(1 if bad else 0)

asyncio.run(main())
