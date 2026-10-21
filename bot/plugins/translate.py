"""
翻译插件
命令：/翻译 <内容>  → 自动检测源语种翻译成对方语言（中<->英）
简单起见只用：中文 → 英文 / 英文 → 中文
"""
from nonebot import on_command
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message

translate = on_command("翻译", priority=20, block=True)


@translate.handle()
async def _(event: GroupMessageEvent):
    text = event.get_plaintext().strip().replace("/翻译", "", 1).strip()
    if not text:
        await translate.finish("用法：/翻译 你好世界")

    try:
        from googletrans import Translator
        async with Translator() as tr:
            detect = await tr.detect(text)
            dest = "zh-CN" if detect.lang != "zh-CN" else "en"
            res = await tr.translate(text, dest=dest)

        src_name = {"zh-CN": "中文", "en": "英语", "ja": "日语"}.get(res.src, res.src)
        dst_name = {"zh-CN": "中文", "en": "英语"}.get(res.dest, res.dest)
        await translate.finish(
            Message(f"🌐 {src_name} → {dst_name}\n{res.text}")
        )
    except Exception as e:
        await translate.finish(f"翻译失败：{type(e).__name__}\n请检查网络")
