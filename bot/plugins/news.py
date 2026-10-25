"""
新闻早报 —— 每天六十秒，阿萨尔替你读报

命令：新闻 / 早报 / 60s / 每日新闻

数据源：https://news.topurl.cn/api
- 免 key、不限次（实测），返回当日时事要闻 + 农历 + 每日一句
- 备选源都试过：60s.viki.moe 被 Cloudflare 拦、vvhan/52vmy 超时、03c3.cn 502，
  只有这个通。哪天它挂了，换 fetch() 里的 URL 就行。
"""
import aiohttp
from nonebot import on_command
from nonebot.rule import to_me
from nonebot.adapters.onebot.v11 import Message

news_cmd = on_command(
    "新闻", aliases={"早报", "60s", "每日新闻", "看新闻"},
    rule=to_me(), priority=20, block=True,
)

API = "https://news.topurl.cn/api"
COUNT = 10          # 报几条
TIMEOUT = 15


@news_cmd.handle()
async def _():
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(
                API,
                params={"count": COUNT},
                timeout=aiohttp.ClientTimeout(total=TIMEOUT),
            ) as r:
                d = await r.json(content_type=None)
    except Exception as e:
        await news_cmd.finish(f"今天的报童没来（{type(e).__name__}），改天再问。")
        return

    if (d or {}).get("code") != 200:
        await news_cmd.finish("报童把今天的报纸弄丢了，改天再问。")
        return

    data = d.get("data") or {}
    items = data.get("newsList") or []
    if not items:
        await news_cmd.finish("今天的报纸是空白的，改天再问。")
        return

    # 公历抬头（源数据里 cMonth/cDay 是公历月日）
    cal = data.get("calendar") or {}
    head = ""
    if cal.get("cMonth") and cal.get("cDay"):
        head = f"{cal.get('cYear', '')}年{cal['cMonth']}月{cal['cDay']}日"

    lines = ["📰 每日要闻"]
    if head:
        lines[0] = f"📰 {head.strip()}"
    lines.append("─────────────")
    for i, it in enumerate(items[:COUNT], 1):
        title = (it.get("title") or "").strip()
        if title:
            lines.append(f"{i}. {title}")

    # 每日一句当落款，有就带
    sen = (data.get("sentence") or {}).get("sentence") or ""
    author = ((data.get("sentence") or {}).get("author") or "").strip("·.")
    if sen:
        lines.append("")
        lines.append(f"「{sen}」——{author}" if author else f"「{sen}」")

    await news_cmd.finish(Message("\n".join(lines)))
