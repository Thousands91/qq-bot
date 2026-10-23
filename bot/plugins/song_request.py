"""
点歌

群里发 /点歌 晴天  → 机器人找到歌，发一条语音 / 分享卡片

音源说明
---------
网易云的 free 外链早在 2021 年就关了，官方 openapi 又要会员。
这里走第三方聚合接口拿音频流，属于"能响就行"的方案：
- 单曲可能只返回 45 秒试听片段（版权方限制），也可能给整首
- 接口本身是公益性质的，随时可能失效

因此做了三层兜底：
1. 取流 → 有音频 → 发语音
2. 取流失败 → 发分享卡片（歌名/歌手/链接）
3. 搜索失败 → 如实告诉用户没找到
"""
import re
from datetime import datetime
from pathlib import Path

import aiohttp
from nonebot import on_command
from nonebot.exception import FinishedException
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message, MessageSegment
from nonebot.params import CommandArg

song_cmd = on_command("点歌", aliases={"听歌", "来首歌"}, priority=20, block=True)

SEARCH = "https://music.163.com/api/search/get"
# 第三方取流：给了 id 就返回 mp3 二进制
STREAM = "https://api.injahow.cn/meting/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# 超过这个大小就不下载了，QQ 传大文件容易超时
MAX_BYTES = 16 * 1024 * 1024
# 搜索回来的候选，最多往下试几个
TRY_N = 6
# 语音时长上限：先设很宽，等实测出 QQ 到底卡在哪一秒再收紧。
# 见 bot/data/voice_probe.log —— 下面 probe() 会把每次发送的时长和结果都记下来。
MAX_VOICE_SEC = 300
# 公开群聊里按这两个开关过滤：不含 VIP 曲目（免费也拿不到音频）、剔除现场/伴奏版
FILTER_VIP = True
BAD_WORDS = ("伴奏", "纯音乐", "ktv", "instrumental", "inst.", "remix", "dj", "慢摇")


@song_cmd.handle()
async def _(event: GroupMessageEvent, arg: Message = CommandArg()):
    # 命令前缀可能是空串（裸词"点歌"就能触发），这时 get_plaintext() 里
    # 没有"/点歌"可替换，整句会被当成歌名——所以必须走 CommandArg
    kw = arg.extract_plain_text().strip()

    if not kw:
        await song_cmd.finish("想听什么？说个歌名，或者一句歌词也行。")

    await song_cmd.send(f"翻柜子找「{kw}」，稍等一下……")

    songs = await search(kw)
    songs = [s for s in songs if usable(s, kw)]
    if not songs:
        await song_cmd.finish(f"「{kw}」这几个字，我在曲子里翻不着。换个说法试试？")

    # 用户写了歌手名，就把这位歌手的版本排到前头
    songs = rank_by_artist(songs, kw)

    # 同名歌很多，按顺序试，取第一个真能拿到音频的
    card = songs[0]
    for s in songs[:TRY_N]:
        audio, sec, err = await fetch_audio(s["id"])
        if not audio:
            continue
        card = s
        if sec and sec > MAX_VOICE_SEC:
            # 长到这个地步，语音条肯定装不下了
            await song_cmd.finish(
                Message(f"{build_card(s)}\n\n这首 {sec} 秒，一条语音装不下。点开听吧。")
            )
        try:
            # 长音频发过去要等 NapCat 转 silk 再上传，默认 30 秒的 api_timeout
            # 根本不够，按体积给个宽裕的余量。
            _t = 60 + len(audio) // (200 * 1024)
            await song_cmd.send(MessageSegment.record(audio), _timeout=_t)
            probe(sec, len(audio), "ok", "")
            return
        except FinishedException:
            # finish() 是靠抛这个异常结束的，别当成"发送失败"记进日志
            raise
        except BaseException as e:
            # BaseException 不是手滑：音频往 WS 里塞是同步的，长音频能卡住
            # 整个事件循环，卡太久会被 CancelledError 打断。这种也得兜住，
            # 否则异常漏出去就是一个红色堆栈，用户那边什么也收不到。
            probe(sec, len(audio), "fail", f"{type(e).__name__}|{_t if '_t' in dir() else '?'}")
            await song_cmd.finish(
                Message(f"{build_card(s)}\n\n这首 {sec} 秒，语音条递不过去。点开听吧。")
            )

    # 全都拿不到音频，退回卡片
    await song_cmd.finish(
        Message(f"{build_card(card)}\n\n曲子我调不出来，只能给您递个名目。")
    )


LOG = Path(__file__).resolve().parent.parent / "data" / "voice_probe.log"


def probe(sec: int, size: int, result: str, err: str) -> None:
    """记一条：这次发了多少秒，成没成。

    QQ 语音条到底能有多长，官方没说，各家说法不一。与其猜，不如让它自己
    记：跑一段时间翻日志，就能看出失败是从第几秒开始出现的。
    """
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}\t{sec}s\t"
                    f"{size // 1024}KB\t{result}\t{err}\n")
    except Exception:
        pass


async def search(keyword: str) -> list:
    try:
        async with aiohttp.ClientSession(headers={"User-Agent": UA, "Referer": "https://music.163.com/"}) as sess:
            async with sess.get(
                SEARCH,
                params={"s": keyword, "type": 1, "limit": 10, "offset": 0},
                timeout=aiohttp.ClientTimeout(total=12),
            ) as r:
                d = await r.json(content_type=None)
        raw = ((d.get("result") or {}).get("songs")) or []
        out = []
        for s in raw:
            out.append({
                "id": s["id"],
                "name": s.get("name", ""),
                "artists": "/".join(a.get("name", "") for a in (s.get("artists") or [])),
                "album": (s.get("album") or {}).get("name", ""),
                "sec": int((s.get("duration") or 0) // 1000),
                "fee": s.get("fee", 0),
            })
        return out
    except Exception:
        return []


def _norm(t: str) -> str:
    """只留汉字和字母数字，用来比对名字。"""
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]", "", (t or "").lower())


def usable(s: dict, keyword: str) -> bool:
    """过滤掉注定发不出声的条目。

    网易云的搜索很"宽容"，输一串乱码也能返 10 条不相干的歌，所以两件事：
    1. 歌名得跟关键字真的沾边（互相包含，按去符号后比对）
    2. 剔除伴奏 / 纯音乐 / DJ 版（这些是给翻唱伴奏用的，不是给人听的）
    """
    if FILTER_VIP and s.get("fee") == 1:
        return False
    name = _norm(s["name"])
    kws = [k for k in re.split(r"[\s,，、/]+", keyword.strip()) if k]
    if not kws:
        return True
    full = _norm(keyword)
    # 歌名含整串关键字，或整串含歌名，或至少命中一个词
    if full and (full in name or (name and name in full)):
        return True
    if not any(_norm(k) in name for k in kws):
        return False
    if any(w in s["name"].lower() for w in BAD_WORDS):
        return False
    return True


async def fetch_audio(song_id: int):
    """返回 (音频 bytes 或 None, 时长秒, 错误说明)"""
    url = f"{STREAM}?type=url&id={song_id}"
    try:
        async with aiohttp.ClientSession(headers={"User-Agent": UA}) as sess:
            async with sess.get(url, timeout=aiohttp.ClientTimeout(total=30)) as r:
                if r.status != 200:
                    return None, 0, f"HTTP {r.status}"
                ctype = (r.headers.get("Content-Type") or "").lower()
                # 拿不到音频时接口会回一个空 text/html，正好挡住
                if "audio" not in ctype and "octet-stream" not in ctype:
                    return None, 0, "不是音频"
                size = int(r.headers.get("Content-Length") or 0)
                # 完整版动辄十几兆，超了就不下了，别白等一分钟
                if size > MAX_BYTES:
                    return None, 0, "文件过大"
                # 分块读，超过上限就停，避免把内存吃光
                chunks, got = [], 0
                async for chunk in r.content.iter_chunked(64 * 1024):
                    got += len(chunk)
                    if got > MAX_BYTES:
                        return None, 0, "文件过大"
                    chunks.append(chunk)
        data = b"".join(chunks)
        if len(data) < 20 * 1024:
            return None, 0, "文件过小"
        return data, mp3_seconds(data), ""
    except Exception as e:
        return None, 0, type(e).__name__


def rank_by_artist(songs: list, keyword: str) -> list:
    """关键字里带了歌手，就把该歌手的版本提前。

    网易云大量原唱因版权下架，搜出来多是翻唱。这里只保证"同名翻唱里
    优先挑歌手对得上的"，挑不到也不假装它是原曲。
    """
    hits = [s for s in songs if s["artists"] and s["artists"] in keyword]
    rest = [s for s in songs if s not in hits]
    return hits + rest


def mp3_seconds(data: bytes) -> int:
    """不依赖第三方库，从 MP3 帧头估算时长。"""
    if len(data) < 4096:
        return 0
    i = 0
    if data[:3] == b"ID3":
        sz = ((data[6] & 0x7F) << 21) | ((data[7] & 0x7F) << 14) | \
             ((data[8] & 0x7F) << 7) | (data[9] & 0x7F)
        i = 10 + sz
    limit = min(len(data) - 4, 65536)
    while i < limit and not (data[i] == 0xFF and (data[i + 1] & 0xE0) == 0xE0):
        i += 1
    if i >= limit:
        return 0
    br_idx = (data[i + 2] >> 4) & 0xF
    bitrates = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0]
    br = bitrates[br_idx] * 1000
    if not br:
        return 0
    return int(len(data) * 8 / br)


def build_card(s: dict) -> str:
    artist = s["artists"] or "佚名"
    return (
        f"🎵 {s['name']}\n"
        f"　　{artist}"
        f"{'　《' + s['album'] + '》' if s.get('album') else ''}\n"
        f"　　https://music.163.com/song?id={s['id']}"
    )
