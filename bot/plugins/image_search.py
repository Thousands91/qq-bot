"""
随机表情包 / 搜图

调用 Lolicon API 返回二次元色图（如果配置了 LOLICON_TOKEN）。
不要的话关掉即可。
"""
import os
import random

import aiohttp
from nonebot import on_command
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message

TOKEN = os.getenv("LOLICON_TOKEN", "")

# 一些公开的图源 endpoint
RANDOM_IMG_APIS = [
    # 动漫综合
    "https://www.dmoe.cc/random.php?return=json",
    # 风景 / 二次元
    "https://api.sevin.cn/api/acg_img/?return=json",
]

image_search = on_command("色图", aliases={"来点色图", "整点涩图"}, priority=20, block=True)


@image_search.handle()
async def _(event: GroupMessageEvent):
    # 50% 走 Lolicon，50% 走随机图
    if TOKEN and random.random() < 0.5:
        url = await fetch_lolicon()
    else:
        url = await fetch_random_img()

    if not url:
        await image_search.finish("获取图片失败，请稍后再试 😭")
        return

    await image_search.finish(Message(f"[CQ:image,file={url},cache=0]"))


async def fetch_lolicon() -> str:
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(
                "https://api.lolicon.app/setu/v2",
                params={"num": 1, "r18": 0, "token": TOKEN},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()
                if data.get("data"):
                    return data["data"][0]["urls"].get("original") or \
                           data["data"][0]["urls"].get("regular", "")
    except Exception:
        pass
    return ""


async def fetch_random_img() -> str:
    api = random.choice(RANDOM_IMG_APIS)
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(
                api,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()
                # 兼容多种字段名
                return (
                    data.get("imgurl")
                    or data.get("img_url")
                    or data.get("image_url")
                    or (data.get("img") or "")
                )
    except Exception:
        return ""
