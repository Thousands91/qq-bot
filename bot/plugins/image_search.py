"""
随机图片

- 看图：二次元插画（Lolicon）。私聊开放 R18，群聊只走全年龄
- 看景：真人摄影图（picsum.photos，风景/静物，全年龄）

这个区分不靠参数自觉，靠 isinstance 判定会话类型。
"""
import os
import random

import aiohttp
from nonebot import on_command
from nonebot.adapters.onebot.v11 import (
    GroupMessageEvent,
    Message,
    PrivateMessageEvent,
)

TOKEN = os.getenv("LOLICON_TOKEN", "")

# 全年龄备用图源：dmoe.cc 还活着，sevin.cn 已 404
RANDOM_IMG_APIS = [
    "https://www.dmoe.cc/random.php?return=json",
]

image_search = on_command(
    "看图",
    aliases={"找图", "来点图", "色图", "来点色图", "整点涩图"},
    priority=20,
    block=True,
)


@image_search.handle()
async def _(event: GroupMessageEvent | PrivateMessageEvent):
    private = isinstance(event, PrivateMessageEvent)

    item = await fetch_lolicon(r18=1 if private else 0)

    if item:
        url, is_r18 = item
        # 群聊里绝不能出 R18：拦掉重取一次，重取到的若还带 R18 标记就一条都不发
        if is_r18 and not private:
            item = await fetch_lolicon(r18=0)
            url = ""
            if item and not item[1]:
                url = item[0]
    else:
        url = ""

    if not url:
        url = await fetch_random_img()

    if not url:
        await image_search.finish("图源都不应门，改天再说。")
        return

    await image_search.finish(Message(f"[CQ:image,file={url},cache=0]"))


# —— 看景：真人摄影图，全年龄 ——
scenery = on_command(
    "看景",
    aliases={"风景", "来点风景", "看风景", "摄影"},
    priority=20,
    block=True,
)


@scenery.handle()
async def _():
    # picsum：真实摄影图库。用 seed URL：同一链接永远返回同一张图。
    # 不做预检——图能不能拉成功由 QQ 的服务器说了算，机器人这边探一遍只是白等
    seed = random.randint(0, 999999)
    url = f"https://picsum.photos/seed/{seed}/1200/800.jpg"
    await scenery.finish(Message(f"[CQ:image,file={url},cache=0]"))


async def fetch_lolicon(r18: int = 0):
    """返回 (图片直链, 是否R18)，失败返回 None。"""
    # 默认拿 regular（约 1200px），原图动辄 20MB，QQ 发不出去
    params = {"num": 1, "r18": r18, "size": "regular"}
    if TOKEN:
        params["token"] = TOKEN
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(
                "https://api.lolicon.app/setu/v2",
                params=params,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data = await resp.json()
                if data.get("error"):
                    return None
                arr = data.get("data") or []
                if not arr:
                    return None
                d = arr[0]
                urls = d.get("urls") or {}
                url = urls.get("regular") or urls.get("original") or ""
                if not url:
                    return None
                is_r18 = bool(d.get("r18"))
                # 上游字段偶尔漏填，用标签再兜一次
                if not is_r18:
                    tags = " ".join(d.get("tags") or []).lower()
                    is_r18 = ("r-18" in tags) or ("r18" in tags)
                return (url, is_r18)
    except Exception:
        return None


async def fetch_random_img() -> str:
    api = random.choice(RANDOM_IMG_APIS)
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(api, timeout=aiohttp.ClientTimeout(total=12)) as resp:
                data = await resp.json()
                return (
                    data.get("imgurl")
                    or data.get("img_url")
                    or data.get("image_url")
                    or ""
                )
    except Exception:
        return ""
