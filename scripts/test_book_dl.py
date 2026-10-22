"""单测古籍匹配与下载"""
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


class _Seg:
    def __init__(self, kind, data):
        self.kind, self.data = kind, data


ob.GroupMessageEvent = object
ob.Message = str
ob.MessageSegment = _Seg
sys.modules["nonebot.adapters"] = ad
sys.modules["nonebot.adapters.onebot.v11"] = ob

spec = importlib.util.spec_from_file_location(
    "bf", "/workspace/qq-bot-project/bot/plugins/book_find.py"
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

print(f"✅ 导入成功，古籍目录 {len(m.CATALOG)} 本\n")

HITS = ["山海经", "山海經", "红楼梦", "紅樓夢", "西游记", "水浒传",
        "三字经", "老残游记", "儒林外史", "下载红楼梦", "红楼梦 下载"]
MISS = ["三体", "活着", "不存在的书", "a"]

print("--- 应该命中 ---")
for kw in HITS:
    b = m.match_old(kw)
    print(f"  {kw:10} -> {('《' + b['title'] + '》 id=' + str(b['id'])) if b else '❌ 未命中'}")

print("\n--- 应该不命中 ---")
for kw in MISS:
    b = m.match_old(kw)
    print(f"  {kw:10} -> {'❌ 误命中 ' + b['title'] if b else '✅ 正确'}")


async def dl():
    print("\n--- 实际下载 ---")
    for kw in ["山海经", "红楼梦"]:
        b = m.match_old(kw)
        if not b:
            continue
        data, err = await m.fetch_txt(b["id"])
        if data:
            head = data[:60].decode("utf-8", "ignore").replace("\n", " ")
            print(f"  《{b['title']}》 {len(data)//1024}KB  {head!r}")
        else:
            print(f"  《{b['title']}》 失败: {err}")


asyncio.run(dl())
