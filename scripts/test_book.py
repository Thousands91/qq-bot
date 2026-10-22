"""脱离 nonebot 单测找书插件的核心函数"""
import asyncio
import importlib.util
import sys
import types

nb = types.ModuleType("nonebot")


class _Matcher:
    def __init__(self, *a, **k):
        pass

    def handle(self):
        return lambda f: f

    async def finish(self, *a, **k):
        raise SystemExit

    async def send(self, *a, **k):
        return None


nb.on_command = lambda *a, **k: _Matcher()
sys.modules["nonebot"] = nb

ad = types.ModuleType("nonebot.adapters")
ob = types.ModuleType("nonebot.adapters.onebot.v11")
ob.GroupMessageEvent = object
ob.Message = str
sys.modules["nonebot.adapters"] = ad
sys.modules["nonebot.adapters.onebot.v11"] = ob

spec = importlib.util.spec_from_file_location(
    "bf", "/workspace/qq-bot-project/bot/plugins/book_find.py"
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
print("✅ 模块导入成功\n")

CASES = [
    ("三体", True),
    ("红楼梦", True),
    ("余华", True),
    ("活着", True),
    ("xqzwvbno这样的书不该存在", False),
    ("", False),
]


async def main():
    for kw, expect in CASES:
        books = await m.search(kw)
        mark = "✅" if bool(books) == expect else "❌"
        print(f"{mark} 【{kw or '(空)'}】{len(books)} 本")
        for b in books[:3]:
            print(f"     {b['title']} | {b['author']} | {b['year']} | {b['url']}")

    # 卡片排版
    books = await m.search("三体")
    lines = ["翻出来了，您看是哪一版。", ""]
    for i, b in enumerate(books[:3], 1):
        year = f"（{b['year']}）" if b["year"] else ""
        lines.append(f"{i}. {b['title']}　{b['author'] or '佚名'}{year}")
        lines.append(f"　　{b['url']}")
    print("\n--- 消息预览 ---")
    print("\n".join(lines))

    print("\n--- 没找到 ---")
    print(f"「xqzwvbno」——{m.random.choice(m.MISS_LINES)}")


asyncio.run(main())
