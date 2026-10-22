"""
关键词自动回复 —— 阿萨尔的一句话应答

规则：只发一条消息，只说一句话。不铺垫、不反问。

用法：改下面 REPLIES 字典即可（每个关键词配多条，随机取一条）。
"""
import os
import random

from nonebot import on_message
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message

ENABLE = os.getenv("ENABLE_KEYWORD_REPLY", "true").lower() == "true"

# ===================== 关键词 → 一句话 =====================
REPLIES = {
    "早上好": [
        "早安，今日开卷，宜读些轻的。",
        "早，我已在店里了，灯刚点上。",
        "早上好，七日之期又少一日。",
    ],
    "晚上好": [
        "晚上好，这个时辰适合读长一点的书。",
        "夜了，灯下看字，会清楚些。🕯️",
        "晚上好，今日可有什么值得记下的？",
    ],
    "你好": [
        "您好，我是阿萨尔，书店的。",
        "您好，要看看书吗？",
    ],
    "晚安": [
        "晚安，灯我吹了。🕯️",
        "晚安，睡前一页闲书最好。",
    ],
    "谢谢": [
        "不必谢，这一条我记下了。",
        "客气了。",
    ],
    "群主": [
        "群主？这一条我的册子里还没收录。",
        "道听途说的，我不写进书里。",
    ],
    "苏丹": [
        "苏丹的心思，我从不猜——猜中了是死，猜不中也是死。",
        "他玩他的牌，我卖我的书。",
        "这城里人人都在折卡，只有我在抄词条。",
    ],
    "苏丹卡": [
        "纵欲、奢靡、征服、杀戮，四类四品，共十六张。",
        "七日为期，折不掉，便是刀斧手的事。",
        "卡是死的，抽卡的人是活的。",
    ],
    "杀戮卡": [
        "这一张，我劝您留着——刀可以不出，但不能没有。",
        "血债最贵，我从不赊账。",
    ],
    "百科全书": [
        "百科全书是我和我的家族一直在编纂的东西。",
        "它必须是我亲眼所见，不能是道听途说。",
    ],
    "书": [
        "书是好东西，可惜读完就住在我脑子里了。",
        "想找什么书？说说看，或许我记得。",
    ],
    "阿萨尔": [
        "我在。",
        "您叫我，是有书要找？",
    ],
    "菜单": [
        "📖 翻书 / 问天 / 看图谱 / 找我说话，四件事。",
    ],
}
# ============================================================

kw_reply = on_message(priority=80, block=False)


@kw_reply.handle()
async def _(event: GroupMessageEvent):
    if not ENABLE:
        return

    text = event.get_plaintext().strip().lower()
    if not text:
        return

    # 精确匹配优先
    for kw, replies in REPLIES.items():
        if text == kw.lower():
            await kw_reply.finish(Message(random.choice(replies)))
            return

    # 包含匹配
    for kw, replies in REPLIES.items():
        if kw.lower() in text:
            await kw_reply.finish(Message(random.choice(replies)))
            return
