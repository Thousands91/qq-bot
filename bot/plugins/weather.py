"""
天气查询 —— 阿萨尔替你望一眼天
命令：/天气 <城市>

默认走 Open-Meteo，不需要任何 key、不限调用次数。
若额外配置了和风天气（QWEATHER_KEY + QWEATHER_API_HOST），则优先用它，
数据更细；不配也照样能用。
"""
import os
from datetime import datetime

import aiohttp
from nonebot import on_command
from nonebot.adapters.onebot.v11 import GroupMessageEvent, PrivateMessageEvent, Message
from nonebot.params import CommandArg

KEY = os.getenv("QWEATHER_KEY", "")
# 和风天气 2024 年起改成"每个账号一个专属域名"（形如 xxxxx.re.qweatherapi.com），
# 旧的 devapi.qweather.com 已停用。不填就退到 Open-Meteo，不影响使用。
HOST = os.getenv("QWEATHER_API_HOST", "").rstrip("/")

weather = on_command("天气", priority=20, block=True)

GEO = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST = "https://api.open-meteo.com/v1/forecast"

# WMO 天气代码 → 中文
WMO = {
    0: "晴", 1: "晴间多云", 2: "多云", 3: "阴",
    45: "有雾", 48: "雾凇",
    51: "毛毛雨", 53: "小雨", 55: "中雨",
    56: "冻毛毛雨", 57: "冻雨",
    61: "小雨", 63: "中雨", 65: "大雨",
    66: "冻雨", 67: "强冻雨",
    71: "小雪", 73: "中雪", 75: "大雪", 77: "米雪",
    80: "阵雨", 81: "强阵雨", 82: "暴雨",
    85: "阵雪", 86: "强阵雪",
    95: "雷阵雨", 96: "雷阵雨伴冰雹", 99: "强雷暴伴冰雹",
}


def wind_dir(deg: float) -> str:
    dirs = ["北", "东北", "东", "东南", "南", "西南", "西", "西北"]
    return dirs[int((deg % 360) / 45 + 0.5) % 8] + "风"


@weather.handle()
async def _(event: GroupMessageEvent | PrivateMessageEvent, arg: Message = CommandArg()):
    # 用 CommandArg 而不是自己 replace 前缀：命令前缀可以是空的（裸词触发），
    # 这时 get_plaintext() 里根本没有 "/天气" 可替换，"天气 北京"整个会被当城市名。
    city = arg.extract_plain_text().strip()

    if not city:
        await weather.finish("您想去哪里？说个地名，我替您看一看天。")

    if KEY and HOST:
        text = await get_qweather(city)
        if text:
            await weather.finish(Message(text))

    text = await get_open_meteo(city)
    await weather.finish(Message(text))


async def get_open_meteo(city: str) -> str:
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(
                GEO,
                params={"name": city, "count": 5, "language": "zh"},
                timeout=aiohttp.ClientTimeout(total=12),
            ) as r:
                g = await r.json()
            if not g.get("results"):
                return f"「{city}」这一地名，我的册子里没有。是不是写错了？"
            # 同名地点常有多个，取人口最多的那个（一般就是大家说的那个城）
            loc = max(g["results"], key=lambda x: x.get("population") or 0)

            async with sess.get(
                FORECAST,
                params={
                    "latitude": loc["latitude"],
                    "longitude": loc["longitude"],
                    "current": "temperature_2m,relative_humidity_2m,"
                               "apparent_temperature,weather_code,"
                               "wind_speed_10m,wind_direction_10m",
                    "daily": "weather_code,temperature_2m_max,"
                             "temperature_2m_min,precipitation_probability_max",
                    "timezone": "auto",
                    "forecast_days": 3,
                },
                timeout=aiohttp.ClientTimeout(total=12),
            ) as r:
                d = await r.json()

        cur = d.get("current") or {}
        daily = d.get("daily") or {}
        if not cur:
            return "册子翻到一半，页错了。稍后再问我。"

        name = loc["name"]
        adm = loc.get("admin1") or loc.get("country") or ""
        desc = WMO.get(cur.get("weather_code"), "说不清")

        lines = [
            f"🕯️ {name}（{adm}）此刻的天",
            "─────────────",
            f"气温　{cur['temperature_2m']:.0f}°C（体感 {cur['apparent_temperature']:.0f}°C）",
            f"天气　{desc}",
            f"风向　{wind_dir(cur['wind_direction_10m'])}"
            f" {cur['wind_speed_10m']:.0f} km/h",
            f"湿度　{cur['relative_humidity_2m']:.0f}%",
        ]

        times = daily.get("time") or []
        if times:
            lines.append("")
            lines.append("往后三日")
            for i in range(min(3, len(times))):
                dt = datetime.strptime(times[i], "%Y-%m-%d")
                label = "今日" if i == 0 else f"{dt.month}月{dt.day}日"
                w = WMO.get(daily["weather_code"][i], "")
                lo = daily["temperature_2m_min"][i]
                hi = daily["temperature_2m_max"][i]
                rain = daily["precipitation_probability_max"][i]
                # 天已经在下（数字≥95）就别再说"雨 100%"了，累赘
                rain_txt = "" if rain >= 95 else f"　雨 {rain}%"
                lines.append(f"{label}　{w}　{lo:.0f}～{hi:.0f}°C{rain_txt}")

        lines.append("")
        lines.append("出门的话，记得看一眼再走。")
        return "\n".join(lines)
    except Exception as e:
        return f"这本书今天翻不开（{type(e).__name__}）。"


async def get_qweather(city: str) -> str:
    """配了和风就用它，数据更细；失败返回空串，交给 Open-Meteo。"""
    headers = {"X-QW-Api-Key": KEY}
    try:
        async with aiohttp.ClientSession(headers=headers) as sess:
            async with sess.get(
                f"{HOST}/geo/v2/city/lookup",
                params={"location": city, "number": 1},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as r1:
                j1 = await r1.json()
            if j1.get("code") != "200" or not j1.get("location"):
                return ""
            loc = j1["location"][0]

            async with sess.get(
                f"{HOST}/v7/weather/now",
                params={"location": loc["id"]},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as r2:
                j2 = await r2.json()
            if j2.get("code") != "200":
                return ""

            now = j2["now"]
            return (
                f"🕯️ {loc['name']}（{loc.get('adm1', '')}）此刻的天\n"
                f"─────────────\n"
                f"气温　{now['temp']}°C（体感 {now['feelsLike']}°C）\n"
                f"天气　{now['text']}\n"
                f"风向　{now['windDir']} {now['windScale']}级\n"
                f"湿度　{now['humidity']}%\n"
                f"能见　{now['vis']} 里\n\n"
                f"出门的话，记得看一眼再走。"
            )
    except Exception:
        return ""
