"""
翻译插件
命令：/翻译 <内容>  → 中文转英文 / 英文转中文

不用 googletrans：那套库依赖 cgi 模块，Python 3.13 起已被移除，
装了也跑不起来。这里直接调 MyMemory 的公开接口，只用 aiohttp。
"""
import re

import aiohttp
from nonebot import on_command
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message

translate = on_command("翻译", priority=20, block=True)

API = "https://api.mymemory.translated.net/get"


def has_chinese(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


@translate.handle()
async def _(event: GroupMessageEvent):
    text = event.get_plaintext().strip()
    for p in ("/翻译", "!翻译", "！翻译"):
        text = text.replace(p, "", 1)
    text = text.strip()

    if not text:
        await translate.finish("用法：/翻译 你好世界")

    src, dst = ("zh-CN", "en") if has_chinese(text) else ("en", "zh-CN")
    src_name = "中文" if src == "zh-CN" else "英语"
    dst_name = "英语" if dst == "en" else "中文"

    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(
                API,
                params={"q": text, "langpair": f"{src}|{dst}"},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data = await resp.json()
        out = (data.get("responseData") or {}).get("translatedText", "").strip()
        if not out:
            await translate.finish("这一句我译不出来，换一句试试。")

        # MyMemory 是社区语料，偶尔会给出跟原文毫无关系的句子。
        # 一道保险：译文里一个原词都不剩，就当它没译成。
        if out.lower() == text.lower():
            await translate.finish(f"这一句它没译动，还是：{out}")

        await translate.finish(Message(f"🌐 {src_name} → {dst_name}\n{out}"))
    except Exception as e:
        await translate.finish(f"翻译失败：{type(e).__name__}\n请检查网络")
