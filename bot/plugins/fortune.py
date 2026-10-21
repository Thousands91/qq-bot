"""
抽签 / 今日运势
命令：抽签 / 运势 / 抽签 <事项>
"""
import random
import datetime

from nonebot import on_command
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message

fortune = on_command("抽签", aliases={"运势"}, priority=20, block=True)

FORTUNES = [
    ("大吉", "🌟", "今天简直是开挂的一天！想做什么都大胆去做吧！"),
    ("吉", "✨", "整体运势很好，保持好心情就能一直顺利下去~"),
    ("中吉", "🌈", "平平淡淡才是真，好运正在悄悄酝酿中~"),
    ("末吉", "🍀", "小小的等待是值得的，耐心一点会有好结果"),
    ("凶", "🌧️", "今天不太顺，低调一点比较稳妥，避免重大决定"),
    ("大凶", "⛈️", "今天真的建议躺平，别跟运气硬碰硬哦~"),
    ("吉凶相半", "🎭", "凡事都可能，看你怎么选了"),
]


@fortune.handle()
async def _(event: GroupMessageEvent):
    today = datetime.date.today()
    # 用 (QQ, 日期) 做种子，保证同一个用户当天是同一个签
    seed_str = f"{today.isoformat()}-{event.user_id}"
    rand = random.Random(seed_str)

    level, emoji, desc = rand.choice(FORTUNES)

    # 5 个 0~99 评分
    scores = {k: rand.randint(40, 99) for k in ["事业", "财运", "爱情", "健康", "学业"]}

    user = event.sender.card or event.sender.nickname
    msg = (
        f"🎴 今日运势 - {user} \n"
        f"🗓 {today.strftime('%Y年%m月%d日')}\n"
        f"─────────────\n"
        f"{emoji} {level}\n\n"
        f"{desc}\n\n"
        f"📊 五维评分：\n"
        f"💼 事业 {scores['事业']}   💰 财运 {scores['财运']}\n"
        f"💗 爱情 {scores['爱情']}   💪 健康 {scores['健康']}\n"
        f"📚 学业 {scores['学业']}\n\n"
        f"🔮 宜：撸猫 / 听歌 / 摸鱼\n"
        f"⚠️ 忌：和老板顶嘴 / 拖延\n"
    )

    await fortune.finish(Message(msg))
