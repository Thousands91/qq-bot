"""
天气查询
命令：/天气 <城市>

免费 key：和风天气 https://dev.qweather.com (一天 1000 次调用)
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
    city = event.get_plaintext().strip().replace("/天气", "", 1).strip()
    if not city:
        await weather.finish("用法：/天气 北京")

    if not KEY:
        await weather.finish("未配置和风天气 QWEATHER_KEY，请先在 .env 中填写")

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
                return f"找不到城市「{city}」😢"
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
                return f"天气接口返回错误：{j2.get('code')}"

            now = j2["now"]
            return (
                f"🌤️ {city_name}（{adm}）当前天气\n"
                f"气温：{now['temp']}°C（体感 {now['feelsLike']}°C）\n"
                f"天气：{now['text']}\n"
                f"风向风速：{now['windDir']} {now['windScale']}级\n"
                f"相对湿度：{now['humidity']}%\n"
                f"能见度：{now['vis']} km"
            )
    except Exception as e:
        return f"查询失败：{type(e).__name__}"
