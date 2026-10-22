"""
天气查询 —— 阿萨尔替你望一眼天
命令：/天气 <城市>

免费 key：和风天气 https://dev.qweather.com （一天 1000 次调用）
"""
import os

import aiohttp
from nonebot import on_command
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message

KEY = os.getenv("QWEATHER_KEY", "")
HOST = os.getenv("QWEATHER_API_HOST", "https://devapi.qweather.com")

weather = on_command("天气", priority=20, block=True)


@weather.handle()
async def _(event: GroupMessageEvent):
    city = event.get_plaintext().strip()
    for p in ("/天气", "!天气", "！天气"):
        city = city.replace(p, "", 1)
    city = city.strip()

    if not city:
        await weather.finish("您想去哪里？说个地名，我替您看一看天。")

    if not KEY:
        await weather.finish("这一条我还查不了——店里没订天气的册子。")

    text = await get_weather(city)
    await weather.finish(Message(text))


async def get_weather(city: str) -> str:
    headers = {"X-QW-Api-Key": KEY}
    try:
        async with aiohttp.ClientSession(headers=headers) as sess:
            # 1) 城市 ID 查找
            async with sess.get(
                f"{HOST}/geo/v2/city/lookup",
                params={"location": city, "number": 1},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as r1:
                j1 = await r1.json()
            if j1.get("code") != "200" or not j1.get("location"):
                return f"「{city}」这一地名，我的册子里没有。是不是写错了？"
            loc = j1["location"][0]
            city_name = loc["name"]
            adm = loc.get("adm1", "")
            loc_id = loc["id"]

            # 2) 当前天气
            async with sess.get(
                f"{HOST}/v7/weather/now",
                params={"location": loc_id},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as r2:
                j2 = await r2.json()
            if j2.get("code") != "200":
                return f"册子翻到一半，页错了（{j2.get('code')}）。稍后再问我。"

            now = j2["now"]
            return (
                f"🕯️ {city_name}（{adm}）此刻的天\n"
                f"─────────────\n"
                f"气温　{now['temp']}°C（体感 {now['feelsLike']}°C）\n"
                f"天气　{now['text']}\n"
                f"风向　{now['windDir']} {now['windScale']}级\n"
                f"湿度　{now['humidity']}%\n"
                f"能见　{now['vis']} 里\n\n"
                f"出门的话，记得看一眼再走。"
            )
    except Exception as e:
        return f"这本书今天翻不开（{type(e).__name__}）。"
