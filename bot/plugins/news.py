"""
新闻早报 —— 每天六十秒，阿萨尔替你读报

命令：新闻 / 早报 / 60s / 每日新闻 / 看新闻

数据源
------
主源 https://news.topurl.cn/api —— 当日时事要闻 + 农历 + 每日一句
备用 https://uapis.cn/api/v1/misc/hotboard?type=weibo —— 微博热搜

两个源都只给标题，没有正文。宁可只报标题，也不让大模型去"推测"内容——
猜出来的东西就是假新闻。想看细节点每条后面的链接。
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
FALLBACK = "https://uapis.cn/api/v1/misc/hotboard"
COUNT = 10          # 报几条
TIMEOUT = 15


async def fetch_headlines():
    """取 (抬头, [(标题, 链接)], 落款)。主源不通就走热搜榜。"""
    items, head, tail = [], "", ""
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(
                API,
                params={"count": COUNT},
                timeout=aiohttp.ClientTimeout(total=TIMEOUT),
            ) as r:
                d = await r.json(content_type=None)
        if (d or {}).get("code") == 200:
            data = d.get("data") or {}
            for x in (data.get("newsList") or []):
                title = (x.get("title") or "").strip()
                if title:
                    items.append((title, (x.get("url") or x.get("link") or "").strip()))
            cal = data.get("calendar") or {}
            if cal.get("cMonth") and cal.get("cDay"):
                head = f"{cal.get('cYear', '')}年{cal['cMonth']}月{cal['cDay']}日"
            sen = (data.get("sentence") or {}).get("sentence") or ""
            author = ((data.get("sentence") or {}).get("author") or "").strip("·.")
            if sen:
                tail = f"「{sen}」——{author}" if author else f"「{sen}」"
    except Exception:
        pass

    if not items:
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.get(
                    FALLBACK,
                    params={"type": "weibo"},
                    timeout=aiohttp.ClientTimeout(total=TIMEOUT),
                ) as r:
                    d = await r.json(content_type=None)
            for x in ((d or {}).get("list") or []):
                title = (x.get("title") or "").strip()
                if title:
                    items.append((title, (x.get("url") or "").strip()))
            head = "今日微博热搜"
        except Exception:
            pass

    return head, items, tail


@news_cmd.handle()
async def _():
    head, items, tail = await fetch_headlines()
    if not items:
        await news_cmd.finish("今天的报纸是空白的，改天再问。")
        return

    items = items[:COUNT]

    lines = [f"📰 {head}" if head else "📰 每日要闻", "─────────────"]
    for i, (title, url) in enumerate(items, 1):
        if url and len(url) <= 80:
            lines.append(f"{i}. {title}\n{url}")
        else:
            # 链接太长（微博的中文全转义成 %XX）就不带，免得整屏都是乱码
            lines.append(f"{i}. {title}")

    if tail:
        lines += ["", tail]

    await news_cmd.finish(Message("\n".join(lines)))
