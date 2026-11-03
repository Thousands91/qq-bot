"""games 插件（掷骰/决斗/猜数字/谜语）全功能测试 —— 上菜单前的把关"""
import asyncio, sys
sys.path.insert(0, "/tmp/phone_pl")
import os
os.environ["OPENAI_API_KEY"] = "sandbox-test-key"
import nonebot
nonebot.init()
from nonebot.adapters.onebot.v11 import Adapter, GroupMessageEvent, Message, MessageSegment
from nonebot.internal.matcher import Matcher
nonebot.get_driver().register_adapter(Adapter)

names = sorted(p.name for p in nonebot.load_plugins("/tmp/phone_pl"))
print("[0] 插件加载:", len([n for n in names if not n.startswith("_")]), "个")

from nonebot.adapters.onebot.v11 import Bot as _OB
_ad = list(nonebot.get_driver()._adapters.values())[0]
BOT = _OB(_ad, "3427943187")

captured = []
async def _fake_finish(cls, message=None, **kw):
    captured.append(message)
    raise nonebot.exception.FinishedException()
Matcher.finish = classmethod(_fake_finish)

ME = "3427943187"

def gevt(text, uid=1561950850, to_me=True):
    return GroupMessageEvent(time=0, self_id=ME, post_type="message",
        message_type="group", sub_type="normal", message_id=9, user_id=uid,
        group_id=590454333, message=Message(text), raw_message=text, font=0,
        sender={"user_id": uid, "nickname": "测试员", "card": ""}, to_me=to_me)

def gevt_at(text, at_uid, uid=1561950850):
    """带 @ 段的消息（决斗用）"""
    msg = Message([MessageSegment.at(at_uid), MessageSegment.text(" " + text)])
    raw = f"[CQ:at,qq={at_uid}] {text}"
    return GroupMessageEvent(time=0, self_id=ME, post_type="message",
        message_type="group", sub_type="normal", message_id=9, user_id=uid,
        group_id=590454333, message=msg, raw_message=raw, font=0,
        sender={"user_id": uid, "nickname": "测试员", "card": ""}, to_me=False)

async def run(matcher, event):
    captured.clear()
    try:
        await matcher.handlers[0](bot=BOT, event=event)
    except nonebot.exception.FinishedException:
        pass
    return captured[0] if captured else None

async def main():
    P = {n: nonebot.get_plugin(n).module for n in names}
    g = P["games"]
    ok = 0

    # ===== 1. 掷骰 =====
    r = await run(g.dice_cmd, gevt("掷骰"))
    assert r and "🎲" in str(r) and "点" in str(r), f"掷骰异常: {r}"
    r = await run(g.dice_cmd, gevt("骰子"))
    assert r and "🎲" in str(r), f"别名'骰子'没进 handler: {r}"
    ok += 1; print("[1] 掷骰（含别名）OK")

    # ===== 2. 决斗 @别人 =====
    r = await run(g.dice_cmd, gevt_at("决斗", 88888888))
    assert r and "🎲" in str(r) and ("赢" in str(r) or "输" in str(r) or "平手" in str(r)), f"决斗异常: {r}"
    ok += 1; print("[2] 决斗 @别人 OK")

    # ===== 3. 决斗 @阿萨尔自己 =====
    r = await run(g.dice_cmd, gevt_at("决斗", int(ME)))
    assert r and "跟我决斗" in str(r), f"@自己决斗没拦: {r}"
    ok += 1; print("[3] 决斗 @阿萨尔自己 → 拒绝 OK")

    # ===== 4. 猜数字：开局 =====
    r = await run(g.guess_start, gevt("猜数字"))
    assert r and "1 到 100" in str(r), f"开局异常: {r}"
    assert 590454333 in g.GUESS_GAMES, "开局没入状态表"
    ans = g.GUESS_GAMES[590454333]["answer"]
    assert 1 <= ans <= 100, f"答案越界: {ans}"
    ok += 1; print("[4] 猜数字开局 OK，本局答案 =", ans)

    # ===== 5. 猜小了 / 猜大了 =====
    g.GUESS_GAMES[590454333] = {"answer": 50, "count": 0}
    r = await run(g.guess_do, gevt("猜 30"))
    assert r and "小了" in str(r), f"猜30应报小了: {r}"
    r = await run(g.guess_do, gevt("猜 88"))
    assert r and "大了" in str(r), f"猜88应报大了: {r}"
    assert g.GUESS_GAMES[590454333]["count"] == 2, "计数没累加"
    ok += 1; print("[5] 猜大了/小了 + 计数 OK")

    # ===== 6. 中文数字 =====
    assert g._parse_guess("猜 五十") == 50, "中文'五十'"
    assert g._parse_guess("猜二十五") == 25, "中文'二十五'"
    assert g._parse_guess("猜一百") == 100, "中文'一百'"
    assert g._parse_guess("猜 一") == 1, "中文'一'"
    r = await run(g.guess_do, gevt("猜 五十"))
    assert r and "就是它" in str(r), f"中文猜中没认: {r}"
    assert 590454333 not in g.GUESS_GAMES, "猜中没清局"
    ok += 1; print("[6] 中文数字 + 猜中收局 OK")

    # ===== 7. 越界 / 乱数不响应 =====
    g.GUESS_GAMES[590454333] = {"answer": 50, "count": 0}
    assert g._parse_guess("猜 999") is None, "999 越界没拦"
    assert g._parse_guess("猜 0") is None, "0 越界没拦"
    r = await run(g.guess_do, gevt("猜 999"))
    assert r is None, f"越界数不该响应: {r}"
    r = await run(g.guess_do, gevt("今天天气不错"))
    assert r is None, f"闲话不该响应: {r}"
    r = await run(g.guess_do, gevt("不玩了"))
    assert r and "那个数是 50" in str(r), f"认输异常: {r}"
    ok += 1; print("[7] 越界不响应 + 闲话不打扰 + 认输 OK")

    # ===== 8. 没开局时一切静默 =====
    r = await run(g.guess_do, gevt("猜 50"))
    assert r is None, "没开局时'猜 50'不该响应"
    r = await run(g.guess_do, gevt("不玩了"))
    assert r is None, "没开局时'不玩了'不该响应"
    ok += 1; print("[8] 没开局全静默 OK")

    # ===== 9. 谜语：出题 + 重复出题 =====
    r = await run(g.riddle_cmd, gevt("谜语"))
    assert r and "说书人出一题" in str(r), f"出题异常: {r}"
    game = g.RIDDLE_GAMES[590454333]
    face, ans2, hint = game["riddle"]
    assert face and ans2 and hint, "谜语三元组不全"
    r = await run(g.riddle_cmd, gevt("谜语"))
    assert r and "还没人猜中" in str(r) and face in str(r), f"重复出题应报旧谜面: {r}"
    ok += 1; print("[9] 谜语出题 + 重复出题报旧题 OK")

    # ===== 10. 提示 =====
    r = await run(g.riddle_answer, gevt("提示"))
    assert r and hint in str(r), f"提示异常: {r}"
    r = await run(g.riddle_answer, gevt("提示"))
    assert r and "给过了" in str(r), f"二次提示没拦: {r}"
    ok += 1; print("[10] 提示 + 二次提示 OK")

    # ===== 11. 抢答：错 / 对 =====
    r = await run(g.riddle_answer, gevt("答 一个绝对错误的答案"))
    assert r and "不对" in str(r), f"错答异常: {r}"
    assert 590454333 in g.RIDDLE_GAMES, "错答不该清局"
    r = await run(g.riddle_answer, gevt(f"答 {ans2}"))
    assert r and "答对了" in str(r), f"对答没认: {r}"
    assert 590454333 not in g.RIDDLE_GAMES, "答对没清局"
    ok += 1; print("[11] 抢答错/对 OK")

    # ===== 12. 揭晓 + 没局静默 =====
    await run(g.riddle_cmd, gevt("谜语"))
    r = await run(g.riddle_answer, gevt("揭晓"))
    assert r and "谜底是" in str(r), f"揭晓异常: {r}"
    assert 590454333 not in g.RIDDLE_GAMES, "揭晓没清局"
    r = await run(g.riddle_answer, gevt("答 雨"))
    assert r is None, "没局时抢答不该响应"
    r = await run(g.riddle_answer, gevt("揭晓"))
    assert r is None, "没局时揭晓不该响应"
    ok += 1; print("[12] 揭晓 + 没局静默 OK")

    # ===== 13. 互踩检查：谜局挂着时普通闲话不打扰 =====
    await run(g.riddle_cmd, gevt("谜语"))
    r = await run(g.guess_do, gevt("今天天气不错"))
    assert r is None, "guess_do 吃了闲话"
    r = await run(g.riddle_answer, gevt("在吗"))
    assert r is None, "riddle_answer 吃了闲话"
    await run(g.riddle_answer, gevt("揭晓"))  # 收尾
    ok += 1; print("[13] 游戏监听不误吃普通消息 OK")

    print(f"\n=== games 全部 {ok}/13 组测试通过 ===")

asyncio.run(main())
