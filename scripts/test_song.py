"""脱离 nonebot 单测点歌插件的核心函数"""
import asyncio
import importlib.util
import sys
import types

# --- 造假 nonebot 模块，让插件能被导入 ---
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

ad_mod = types.ModuleType("nonebot.adapters")
ob_mod = types.ModuleType("nonebot.adapters.onebot.v11")


class _Msg(str):
    pass


class _Seg:
    @staticmethod
    def record(b):
        return ("RECORD", len(b))


ob_mod.GroupMessageEvent = object
ob_mod.Message = _Msg
ob_mod.MessageSegment = _Seg
sys.modules["nonebot.adapters"] = ad_mod
sys.modules["nonebot.adapters.onebot.v11"] = ob_mod

spec = importlib.util.spec_from_file_location("sr", "/workspace/qq-bot-project/bot/plugins/song_request.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
print("✅ 模块导入成功\n")

CASES = [
    ("晴天 周杰伦", True),
    ("起风了", True),
    ("xqzwvbno这样的歌应该不存在", False),
    ("zzzqqqxxx", False),
]


async def main():
    for kw, expect in CASES:
        raw = await m.search(kw)
        songs = [s for s in raw if m.usable(s, kw)]
        print(f"【{kw}】搜到 {len(raw)} 首，过滤后剩 {len(songs)} 首")
        if not songs:
            assert not expect, f"意外无结果: {kw}"
            print("    → 正确返回空（会回'翻不着'）\n")
            continue
        assert expect, f"意外有结果: {kw}"
        ranked = m.rank_by_artist(songs, kw)
        hit_n = len([s for s in songs if s["artists"] and s["artists"] in kw])
        if hit_n:
            head = ranked[:hit_n]
            assert all(s["artists"] in kw for s in head), "排序失败"
            print(f"    → 歌手命中 {hit_n} 首，已置顶")

        for s in ranked[:3]:
            audio, sec, err = await m.fetch_audio(s["id"])
            if audio:
                print(f"    {s['name']} - {s['artists']}  {len(audio)//1024}KB / {sec}秒  可发语音={sec<=m.MAX_VOICE_SEC}")
            else:
                print(f"    {s['name']} - {s['artists']}  取流失败[{err}]")
        print()

    print("卡片样例：")
    print(m.build_card({"name": "晴天", "artists": "周杰伦", "album": "叶惠美", "id": 186016}))


asyncio.run(main())
