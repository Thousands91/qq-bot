"""
入群欢迎插件
新成员进群自动 @ 欢迎
"""
import os

from nonebot import on_notice
from nonebot.adapters.onebot.v11 import Bot, GroupIncreaseNoticeEvent

ENABLE = os.getenv("ENABLE_WELCOME", "true").lower() == "true"

welcome = on_notice(priority=5)


@welcome.handle()
async def _(bot: Bot, event: GroupIncreaseNoticeEvent):
    if not ENABLE:
        return
    if event.group_id == 0:
        return

    welcomes = [
        f"欢迎 [CQ:at,qq={event.user_id}] 加入群聊！🎉\n请先看群公告哦~",
        f"啪嗒~ 🌟 新朋友 [CQ:at,qq={event.user_id}] 入群啦！请多关照~",
        f"叮咚~ 🚪 [CQ:at,qq={event.user_id}] 加入了群聊，一起愉快玩耍吧！",
    ]

    import random
    msg = random.choice(welcomes)

    try:
        await bot.call_api(
            "send_group_msg",
            group_id=event.group_id,
            message=msg,
        )
    except Exception:
        pass
