"""闭嘴开关 v2 专项测试：叫停只锁互怼对象，其他群友照常聊"""
import asyncio, sys
sys.path.insert(0, "/tmp/phone_pl")
sys.path.insert(0, "/tmp/phone_pl/plugins")
import os
os.environ['OPENAI_API_KEY'] = 'sandbox-test-key'
import nonebot
nonebot.init()
from nonebot.internal.matcher import Matcher
from nonebot.adapters.onebot.v11 import Adapter, GroupMessageEvent, Message
nonebot.get_driver().register_adapter(Adapter)

plugins = nonebot.load_plugins("/tmp/phone_pl")
m = nonebot.get_plugin("ai_chat").module
from nonebot.adapters.onebot.v11 import Bot as _OB
_ad = list(nonebot.get_driver()._adapters.values())[0]
BOT = _OB(_ad, "3427943187")

# ---- 桩 ----
captured = []
async def fake_finish(cls, message=None, **kw):
    captured.append(message)
    raise nonebot.exception.FinishedException()
Matcher.finish = classmethod(fake_finish)  # 坑31：必须 classmethod，否则捕获恒 None

llm_calls = []
async def fake_llm(messages, extra_system=""):
    llm_calls.append(messages)
    return "（测试回答）"
m.call_llm = fake_llm
async def fake_roster(bot, gid):
    return "1=甲"
m._group_roster = fake_roster

JIU = 111   # 互怼对象（鸠）
USER = 1561950850  # 普通群友（喊停的人）
GID = 590454333

def mk_event(text, uid):
    return GroupMessageEvent(
        time=0, self_id="3427943187", post_type="message", message_type="group",
        sub_type="normal", message_id=42, user_id=uid, group_id=GID,
        message=Message(text), raw_message=text, font=0,
        sender={"user_id": uid, "nickname": "谁", "card": ""},
        to_me=True)

async def run(text, uid):
    captured.clear(); llm_calls.clear()
    try:
        await m.ai_chat.handlers[0](bot=BOT, event=mk_event(text, uid), state={})
    except nonebot.exception.FinishedException:
        pass
    return captured

def reset():
    m._MUTE_UNTIL.clear(); m._MUTE_TARGET.clear()
    m._TRIGGER_LOG.clear(); m._DUP.clear()

async def main():
    reset()
    # 1. 鸠连续触发阿萨尔回复两轮（乒乓进行中）
    c = await run("跟我说说天气", JIU); assert c and llm_calls, "鸠第一轮没回"
    c = await run("再说说吃的", JIU);   assert c and llm_calls, "鸠第二轮没回"
    print("[1] 鸠与阿萨尔互 @ 两轮（互怼进行中）OK")

    # 2. 用户喊停 → 回确认语，且锁定鸠为互怼对象
    c = await run("停止", USER)
    assert c and ("我先不说话" in str(c[0]) or "我闭口" in str(c[0])), f"喊停没确认: {c}"
    assert m._MUTE_TARGET[GID] == {JIU}, f"互怼对象锁定错误: {m._MUTE_TARGET.get(GID)}"
    print("[2] 用户喊停 → 确认语 + 互怼对象=鸠 OK")

    # 3. 静音期内鸠再 @ → 完全静默（连"我先不说话"都不回，防被接住续环）
    c = await run("你还理我吗", JIU)
    assert c == [] and not llm_calls, f"互怼对象没被静默: {c}"
    print("[3] 静音期内鸠 @ → 一声不吭 OK")

    # 4. 静音期内普通群友 @ → 照常回复（核心新行为）
    c = await run("今天天气不错啊", USER)
    assert c and llm_calls, f"普通群友被误伤: cap={c} llm={llm_calls}"
    print("[4] 静音期内普通群友 @ → 照常回复 OK")

    # 5. 用户喊"继续" → 解除；鸠重新得到回应
    c = await run("继续", USER)
    assert c and "说吧" in str(c[0]), f"继续没解除: {c}"
    assert not m._MUTE_TARGET.get(GID), "解除后 target 没清"
    c = await run("那我们接着聊吧", JIU)
    assert c and llm_calls, "解除后鸠没得到回应"
    print("[5] 继续 → 解除，鸠恢复可对话 OK")

    # 6. 无人触发过就喊停 → 不锁任何人，静音期内大家照常
    reset()
    c = await run("停止", USER)
    assert c and m._MUTE_TARGET[GID] == set(), f"没人互怼却锁了人: {m._MUTE_TARGET.get(GID)}"
    c = await run("聊两句", USER)
    assert c and llm_calls, "空锁定时普通群友被拦"
    print("[6] 没有互怼对象时喊停 → 不误锁任何人 OK")

    # 7. 触发最多的才是互怼对象：用户先触发 1 次，鸠触发 2 次 → 锁鸠不锁用户
    reset()
    await run("你好", USER)
    await run("聊聊天", JIU)
    await run("再聊聊天", JIU)
    c = await run("停止", USER)
    assert m._MUTE_TARGET[GID] == {JIU}, f"应锁鸠: {m._MUTE_TARGET.get(GID)}"
    print("[7] 按触发次数锁定：触发最多的鸠被锁，喊停人自己不锁 OK")

    # 8. 解除后可再次喊停（stop 在静音解除后依然有效）
    c = await run("继续", USER); assert c and "说吧" in str(c[0])
    c = await run("别回了", USER)
    assert c and ("我先不说话" in str(c[0]) or "我闭口" in str(c[0])), "再次喊停失效"
    c = await run("在吗", JIU)
    assert c == [], "第二次静音没拦住鸠"
    print("[8] 循环喊停/解除 OK")

    print("\n===== 闭嘴开关 v2 全部 8 组通过 =====")

asyncio.run(main())
