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
from nonebot.params import CommandArg

translate = on_command("翻译", priority=20, block=True)

API = "https://api.mymemory.translated.net/get"


def has_chinese(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


# MyMemory 的限额警告会伪装成译文返回。认这几个词就够，别把它们当译文发出去。
WARN_MARKS = ("MYMEMORY WARNING", "QUOTA", "USED ALL AVAILABLE",
              "INVALID LANGUAGE PAIR", "PLEASE SELECT TWO DISTINCT")


def _is_warning(out: str) -> bool:
    up = out.upper()
    return any(k in up for k in WARN_MARKS)


@translate.handle()
async def _(event: GroupMessageEvent, arg: Message = CommandArg()):
    # 参数一律从 CommandArg 取：前缀可能是空串（裸词触发），
    # 那时 get_plaintext() 里没有"/翻译"可替换
    text = arg.extract_plain_text().strip()

    if not text:
        await translate.finish("用法：翻译 你好世界")

    src, dst = ("zh-CN", "en") if has_chinese(text) else ("en", "zh-CN")
    src_name = "中文" if src == "zh-CN" else "英语"
    dst_name = "英语" if dst == "en" else "中文"

    # 只把"发请求"包在 try 里。finish() 是靠抛 FinishedException 结束的，
    # 放在 try 内会被下面的 except 截下来，再补发一条"翻译失败：FinishedException"。
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(
                API,
                params={"q": text, "langpair": f"{src}|{dst}"},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data = await resp.json()
    except Exception as e:
        await translate.finish(f"翻译失败：{type(e).__name__}\n请检查网络")
        return

    out = (data.get("responseData") or {}).get("translatedText", "").strip()

    # MyMemory 额度用尽时不是报错，而是把警告原文塞进 translatedText：
    # "MYMEMORY WARNING: YOU USED ALL AVAILABLE FREE TRANSLATIONS FOR TODAY..."
    # 直接发出去，群里看到的就是一坨英文警告。这类返回一律当没译成。
    if not out or _is_warning(out):
        await translate.finish("这一句我译不出来（今日的译纸用完了），明天再问吧。")

    # MyMemory 是社区语料，偶尔会给出跟原文毫无关系的句子。
    # 一道保险：译文跟原文一模一样，就当它没译成。
    if out.lower() == text.lower():
        await translate.finish(f"这一句它没译动，还是：{out}")

    await translate.finish(Message(f"🌐 {src_name} → {dst_name}\n{out}"))
