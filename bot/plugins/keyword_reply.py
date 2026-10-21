"""
关键词自动回复插件

用法：在插件底部 KEYWORDS 列表里改你的群关键词即可。
支持精确匹配、子串匹配。
"""
import os
import random

from nonebot import on_message
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message

ENABLE = os.getenv("ENABLE_KEYWORD_REPLY", "true").lower() == "true"

# ===================== 在这里配置你的关键词 =====================
KEYWORDS = {
    "早上好": ["早安呀 ☀️ 今天也要开心呀~", "嗯...早安！🌞", "早上好鸭~ ☕"],
    "晚上好": ["晚上好~ 🌙", "夜深啦，早点休息哦 🌙", "晚上好！辛苦一天了"],
    "你好": ["你好呀 👋 有什么可以帮你的吗？", "嗨！很高兴见到你", "你好~ 我是机器人小派"],
    "群主": ["群主很懒，什么也没留下..."],
    "菜单": [
        "🤖 机器人功能菜单：\n"
        "┣━ /抽签 - 今日运势\n"
        "┣━ /运势 - 同一功能\n"
        "┣━ /天气 <城市> - 查天气\n"
        "┣━ /翻译 <内容> - 中英互译\n"
        "┣━ /色图 - 随机美图\n"
        "┣━ @我 + 任意问题 - AI 智能问答\n"
        "┗━ /清空记忆 - 重置对话上下文"
    ],
}
# ================================================================

kw_reply = on_message(priority=80, block=False)


@kw_reply.handle()
async def _(event: GroupMessageEvent):
    if not ENABLE:
        return

    text = event.get_plaintext().strip().lower()
    if not text:
        return

    # 精确匹配优先
    for kw, replies in KEYWORDS.items():
        if text == kw.lower():
            await kw_reply.finish(Message(random.choice(replies)))
            return

    # 子串匹配（取第一个命中的）
    for kw, replies in KEYWORDS.items():
        if kw.lower() in text:
            await kw_reply.finish(Message(random.choice(replies)))
            return
