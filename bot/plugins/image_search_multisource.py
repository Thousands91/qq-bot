"""
随机图片

- 色图：二次元插画（Lolicon），仅私聊开放（含 R18）
- 看景：真人摄影图（picsum.photos，风景/静物，全年龄）

这个区分不靠参数自觉，靠 isinstance 判定会话类型。
"""
import asyncio
import hashlib
import os
import random
import re

import aiohttp
from ddgs import DDGS
from nonebot import on_command
from nonebot.params import CommandArg
from nonebot.logger import logger
from nonebot.rule import to_me
from nonebot.adapters.onebot.v11 import (
    GroupMessageEvent,
    Message,
    MessageSegment,
    PrivateMessageEvent,
)

TOKEN = os.getenv("LOLICON_TOKEN", "")

# 全年龄备用图源：dmoe.cc 还活着，sevin.cn 已 404
RANDOM_IMG_APIS = [
    "https://www.dmoe.cc/random.php?return=json",
]

def _private_only(event) -> bool:
    # 色图只开私聊：群聊一律不触发，防止封号风险
    return isinstance(event, PrivateMessageEvent)

# —— 近期已发图去重：每关键词记最近 8 张的 md5，撞车就换源重抽 ——
# 背景：Lolicon 部分标签池极小（实测 tag=王者荣耀 R18 每次返回同一 pid），
# 单源反复出同一张；配合 TBIB 轮庄 + 去重把重复率压下去。
_SEEN_HASHES: dict[str, list[str]] = {}


def _img_seen(query: str, data: bytes) -> bool:
    h = hashlib.md5(data).hexdigest()
    return h in _SEEN_HASHES.get(query or "__random__", [])


def _img_remember(query: str, data: bytes) -> None:
    h = hashlib.md5(data).hexdigest()
    lst = _SEEN_HASHES.setdefault(query or "__random__", [])
    lst.append(h)
    del lst[:-8]


image_search = on_command(
    "色图",
    aliases={"来点色图", "整点涩图"},
    rule=to_me() & _private_only,
    priority=20,
    block=True,
)


@image_search.handle()
async def _(event: GroupMessageEvent | PrivateMessageEvent, arg: Message = CommandArg()):
    private = isinstance(event, PrivateMessageEvent)

    # 命令后面跟的词当搜索标签：「色图 原神」→ 搜原神；多词用空格隔开
    tags = [t for t in arg.extract_plain_text().split() if t]
    query = " ".join(tags)

    item = None
    if private and not tags:
        # 2026-11-12 16:40 用户定版：纯随机 100% 色图——不再轮庄。
        # jitsu 的 r18 池是泳装/内衣级软图（原权重 34%→15% 仍被抽中两次），整体退役；
        # tbib 无标签分支本就强制 rating:explicit（硬池，2026-11-05 定的规矩），
        # 保留作 lolicon 挂掉时的降级源。主路直接放行走下面的 lolicon r18。
        pass
    if private and tags:
        # 带词私聊：Lolicon ↔ TBIB 随机做庄 + 近期去重。
        # 实测 Lolicon 对"王者荣耀"等小池子标签每次返回同一张（上游随机失效），
        # 轮庄利用 TBIB 同词库存（如 honor_of_kings R18 有 26 张）拉低重复率。
        tbib_tags = _ZH_TAG_MAP.get(query)
        if tbib_tags is None:
            # 2026-11-12 22:40 智能链定版：AI 只出朴素英文候选词，
            # 标签对齐全权交给图库目录反查（词元边界+安全词表+explicit库存排序）
            tbib_tags = await _search_tag_candidates(query)
        lolicon_first = random.random() < 0.5
        got_dup = False
        for attempt in range(2):
            use_lolicon = (attempt == 0) == lolicon_first
            if use_lolicon:
                item = await fetch_lolicon(r18=1, tags=tags)
                if item:
                    img = await fetch_image_bytes(item[0]) if item[0] else None
                    if img:
                        if _img_seen(query, img):
                            got_dup = True
                            continue
                        _img_remember(query, img)
                        await image_search.finish(MessageSegment.image(img))
                        return
            else:
                if tbib_tags:
                    _img = await fetch_tbib_bytes(tbib_tags)
                    if _img:
                        if _img_seen(query, _img):
                            got_dup = True
                            continue
                        _img_remember(query, _img)
                        await image_search.finish(MessageSegment.image(_img))
                        return
        if got_dup:
            await image_search.finish(
                f"「{query}」这几册您都翻过了，画师尚未落新笔——改日再来，或有新货。"
            )
        else:
            # 2026-11-12 22:40 用户定版：搜不到就如实说，不发不相关的图充数
            await image_search.finish(
                f"「{query}」的风月册页，图库里未曾收录。冷门的作品，画师们不轻易落笔——换位热门角色，兴许有货。"
            )
        return

    item = await fetch_lolicon(r18=1 if private else 0, tags=tags)

    if item:
        urls, is_r18 = item
        # 群聊里绝不能出 R18：拦掉重取一次，重取到的若还带 R18 标记就一条都不发
        if is_r18 and not private:
            item = await fetch_lolicon(r18=0, tags=tags)
            urls = {}
            if item and not item[1]:
                urls = item[0]
    else:
        urls = {}

    img = await fetch_image_bytes(urls) if urls else None

    # pixiv 图库查无此词 → AI 翻译成英文标签 → 查 Safebooru 二次元图库
    # 群聊：Safebooru 本就是全年龄图库，内容符合群里预期，可用
    # 私聊：用户带着「要色图」的预期，Safebooru 只有全年龄图，宁可不发也不能货不对板
    if img is None and tags and not private:
        booru_tags = await translate_tags(query)
        # 先整串查（多标签取交集）；查不到再逐个标签试（避免一个冷门标签拖垮全部）
        candidates = [booru_tags] if booru_tags else []
        if "," in booru_tags:
            candidates += [t.strip() for t in booru_tags.split(",") if t.strip()]
        for ct in candidates:
            booru_url = await fetch_safebooru(ct)
            if booru_url:
                img = await download_image(booru_url)
                if img:
                    break

    if img is None:
        # 带关键词搜不到就不随机兜底，如实说；不带关键词才走备用图源
        if tags:
            if private:
                # Lolicon 搜不到 → tbib 大库再搜一轮（同为色图库，不货不对板）
                # 中文高频词先直译；其余交给 AI 翻译成 booru 英文标签
                tbib_tags = _ZH_TAG_MAP.get(query)
                if tbib_tags is None:
                    tbib_tags = await _search_tag_candidates(query)
                if tbib_tags:
                    _img = await fetch_tbib_bytes(tbib_tags)
                    if _img:
                        await image_search.finish(MessageSegment.image(_img))
                        return
                    # tbib 空手 → hypnohub 同标签再搜一轮（第三硬池，2026-11-12）
                    _img = await fetch_hypnohub_bytes(tbib_tags)
                    if _img:
                        await image_search.finish(MessageSegment.image(_img))
                        return
                # 2026-11-12 22:40 用户定版：搜不到就如实说，不发不相关的图充数
                await image_search.finish(
                    f"「{query}」的风月册页，图库里未曾收录。冷门的作品，画师们不轻易落笔——换位热门角色，兴许有货。"
                )
                return
            await image_search.finish(f"「{query}」么，架上没有这一册。换个说法，我再替您找找。")
            return
        # 2026-11-12 16:40 用户定版：色图命令 100% 色图——dmoe 随机源（全年龄
        # 混池）退役。lolicon 拉取失败时降级 tbib/hypnohub 双硬池（17:10 起），
        # 还拿不到就诚实报"画送来的路上破损了"，绝不发非色图充数。
        img = await _hard_pool_fallback() or img
    if img is None:
        await image_search.finish("画送来的路上破损了，今日只得作罢，改日再取。")
        return
    await image_search.finish(MessageSegment.image(img))


# —— 看景：真人摄影图，全年龄 ——
scenery = on_command(
    "看景",
    aliases={"风景", "来点风景", "看风景", "摄影"},
    rule=to_me(),
    priority=20,
    block=True,
)


@scenery.handle()
async def _():
    # picsum：真实摄影图库。用 seed URL：同一链接永远返回同一张图。
    # 不做预检——图能不能拉成功由 QQ 的服务器说了算，机器人这边探一遍只是白等
    seed = random.randint(0, 999999)
    url = f"https://picsum.photos/seed/{seed}/1200/800.jpg"
    await scenery.finish(Message(f"[CQ:image,file={url},cache=0]"))


# —— 多图源：tbib.org（Danbooru 系大库，可标签搜索，R18，国内可达） ——
# API 与图床（images/samples/thumbnails）实测全通。sample 采样图约
# 1200px，与 Lolicon regular 同级。tags 用 booru 英文标签体系。
TBIB_API = "https://tbib.org/index.php"
_TBIB_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0"

# 中文高频词 → booru 标签直译（不走 AI 翻译也能用）
_ZH_TAG_MAP = {
    "男": ["1boy", "solo"], "男性": ["1boy", "solo"], "男人": ["1boy", "solo"],
    "帅哥": ["1boy", "solo"], "女": ["1girl"], "女性": ["1girl"], "美女": ["1girl"],
    # 男性向扩展（2026-11-05 实测各标签 TBIB R18 均有货）
    "美男": ["bishounen", "1boy"], "小哥哥": ["bishounen", "1boy"],
    "熟男": ["muscular_male", "male_focus"], "大叔": ["ojisan", "male_focus"],
    "叔叔": ["ojisan", "male_focus"], "爸爸": ["old_man", "male_focus"],
    "男同": ["yaoi", "male_focus"], "耽美": ["yaoi", "male_focus"],
    # 女性向扩展
    "姨": ["milf", "1girl"], "阿姨": ["milf", "1girl"],
    "熟女": ["milf", "1girl"], "御姐": ["milf", "1girl"],
    # 注：亲属词（奶奶/爷爷等）不走映射表——2026-11-12 22:40 起由
    # _search_tag_candidates 智能链（AI候选词→图库目录反查→explicit库存排序）
    # 通用解决，发现一个写一个的映射方式已废弃（用户定版：要智能不要白名单）
    # 王者荣耀（2026-11-05 实测：diaochan 无后缀标签被错标污染为宝可梦内容，禁用；
    # 精确标签 diaochan_(honor_of_kings) 全库仅 1 张全年龄图，聊胜于无）
    "王者荣耀": ["honor_of_kings"], "貂蝉": ["diaochan_(honor_of_kings)"],
    # 苏丹的游戏（2026-11-05 实测：TBIB 25+ 张，正确标签带撇号 sultan's_game，
    # AI 会翻成不存在的 sultans_game，必须手写映射）
    "苏丹的游戏": ["sultan's_game"], "苏丹游戏": ["sultan's_game"],
    # 注：未成年向标签（loli/shota 等）永不收录——红线
}


async def _tbib_query_bytes(tag_str: str) -> bytes | None:
    """单个标签组合查 tbib。失败/无图返回 None。"""
    # 大页抓取(limit=100, pid=0)：小池子标签(如仅 1 张的 diaochan_(honor_of_kings))
    # 在旧版随机 pid 0-3 下有 75% 概率翻到空页而白跑；limit=100 一次拿全整池，
    # 页内 shuffle 保证随机性。大池子只取前 100 张随机，变化性足够。
    url = (f"{TBIB_API}?page=dapi&s=post&q=index&json=1&limit=100"
           f"&tags={tag_str}&pid=0")
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(
                url,
                timeout=aiohttp.ClientTimeout(total=15),
                headers={"User-Agent": _TBIB_UA},
            ) as resp:
                if resp.status != 200:
                    return None
                arr = await resp.json(content_type=None)
                if not arr:
                    return None
                random.shuffle(arr)
                for post in arr[:4]:
                    image = post.get("image", "")
                    directory = post.get("directory", "")
                    if not image or not directory:
                        continue
                    # sample(约1200px) 优先，原图兜底——两者实测都可达
                    urls = [f"https://tbib.org/samples/{directory}/sample_{image}",
                            f"https://tbib.org/images/{directory}/{image}"]
                    for u in urls:
                        try:
                            async with sess.get(
                                u, timeout=aiohttp.ClientTimeout(total=25),
                                headers={"User-Agent": _TBIB_UA},
                            ) as r2:
                                if r2.status == 200:
                                    data = await r2.read()
                                    # QQ 发图 10MB 会拖死：超大图直接换下一张
                                    # (2026-11-05: 5MB 线误杀 diaochan_(honor_of_kings)
                                    #  唯一一张图 5.1MB——放宽到 8MB,留足余量)
                                    if 2048 < len(data) <= 8 * 1024 * 1024:
                                        return data
                        except Exception:
                            continue
                return None
    except Exception:
        return None


async def fetch_tbib_bytes(tags: list[str] | None = None) -> bytes | None:
    """tbib 搜图。tags: booru 英文标签（空 = 纯随机）。失败返回 None，绝不抛错。

    先按全部标签取交集搜；搜不到时逐个标签单独搜兜底——防止 AI 翻译出
    不存在的复合标签（如 silver_hair_girl）导致整链空手。
    """
    if tags:
        norm = []
        for t in tags:
            t = t.strip().replace(" ", "_")
            if t and t not in norm:
                norm.append(t)
        tags = norm or None
    # 冷门标签总图数可能很少，pid 不能翻太深；小页码取一批候选随机挑。
    # 注意：booru API 的标签分隔符必须用裸 "+"——走 aiohttp params 会被
    # 编码成 %2B 导致永远搜不到，所以这里手动拼 query string。
    if tags:
        _q = "+".join(["rating:explicit"] + tags)
        data = await _tbib_query_bytes(_q)
        if data:
            return data
        # 交集空手 → 逐标签单独搜（保留"色图"属性 rating:explicit）
        # 注：不做无分级兜底——用户明确要求色图命令只出 R18，
        # 库内未打分级标的图默认全年龄，宁可如实说没有也不发（2026-11-05）。
        for t in tags:
            if t.startswith("rating:"):
                continue
            data = await _tbib_query_bytes(f"rating:explicit+{t}")
            if data:
                return data
        return None
    return await _tbib_query_bytes("rating:explicit")


# —— hypnohub：第三硬池（2026-11-12 17:05 X10 家宽海选实测可达）——
# booru dapi 同族接口，匿名可用。海选结论：danbooru / rule34.xxx / konachan /
# waifu.pics / waifu.im / gelbooru 在 X10 家宽全部不可达（GFW/CF 挑战），
# nekos.best 只剩全年龄分类——hypnohub 是唯一新增的可用硬池。
HYPNO_API = "https://hypnohub.net/index.php"


async def fetch_hypnohub_bytes(tags: list[str] | None = None) -> bytes | None:
    """hypnohub 搜图，硬 R18（恒带 rating:explicit）。失败返回 None，绝不抛错。"""
    tag_q = "+".join(["rating:explicit"] + tags) if tags else "rating:explicit"
    url = (f"{HYPNO_API}?page=dapi&s=post&q=index&json=1&limit=100"
           f"&tags={tag_q}&pid=0")
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(
                url,
                timeout=aiohttp.ClientTimeout(total=15),
                headers={"User-Agent": _TBIB_UA},
            ) as resp:
                if resp.status != 200:
                    return None
                arr = await resp.json(content_type=None)
                if not arr:
                    return None
                random.shuffle(arr)
                for post in arr[:4]:
                    fu = post.get("file_url", "")
                    if not fu:
                        continue
                    try:
                        async with sess.get(
                            fu, timeout=aiohttp.ClientTimeout(total=25),
                            headers={"User-Agent": _TBIB_UA},
                        ) as r2:
                            if r2.status == 200:
                                data = await r2.read()
                                if 2048 < len(data) <= 8 * 1024 * 1024:
                                    return data
                    except Exception:
                        continue
                return None
    except Exception:
        return None


async def _hard_pool_fallback() -> bytes | None:
    """纯随机兜底：tbib / hypnohub 两个硬池随机先手（摊负载），全空手返回 None。"""
    pool = [fetch_tbib_bytes(None), fetch_hypnohub_bytes(None)]
    random.shuffle(pool)
    for fn in pool:
        img = await fn
        if img:
            return img
    return None


# —— 标签目录自动校正（2026-11-05）——
# 背景：AI 把"苏丹的游戏"翻成不存在的 sultans_game（真实标签是 sultan's_game），
# 这类"圈内写法"（撇号、括号后缀、单复数）词典翻译永远对不上。手写映射表
# 无法穷举，故加通用层：拿 AI 的翻译去查图库自动补全目录，查无此词就逐级
# 缩短前缀拉候选、按相似度挑最接近的真实标签。
# 接口：GET /autocomplete.php?q=<前缀> → JSON [{"label":"tag (N)","value":"tag"}]
# value 是 HTML 转义的（&#039; = 撇号），必须还原。
import html as _html

TBIB_BASE = "https://tbib.org"
_TAG_INDEX_CACHE: dict[str, list[tuple[str, int]]] = {}


async def _tbib_tag_index(prefix: str) -> list[tuple[str, int]]:
    """查标签自动补全目录（前缀匹配），返回 [(标签名, 图数)]。失败返回 []。"""
    key = prefix.lower()
    if key in _TAG_INDEX_CACHE:
        return _TAG_INDEX_CACHE[key]
    url = f"{TBIB_BASE}/autocomplete.php?q={prefix}"
    try:
        async with aiohttp.ClientSession() as sess:
                async with sess.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=15),
                    headers={"User-Agent": _TBIB_UA},
                ) as resp:
                    if resp.status != 200:
                        return []
                arr = await resp.json(content_type=None)
                tags = []
                for it in (arr or []):
                    v = _html.unescape(str(it.get("value", ""))).strip()
                    if not v:
                        continue
                    label = _html.unescape(str(it.get("label", "")))
                    cnt_str = label.rsplit("(", 1)[-1].rstrip(") ").strip()
                    try:
                        cnt = int(cnt_str)
                    except ValueError:
                        cnt = 0
                    tags.append((v, cnt))
                _TAG_INDEX_CACHE[key] = tags
                return tags
    except Exception:
        return []


async def _fix_tbib_tags(tags: list[str]) -> list[str]:
    """校正 AI 翻译的标签：查无此词 → 前缀逐级缩短 → 相似度挑最接近的真实标签。

    校正失败（相似度过低/目录也查不到）就保留原词，由后续查询层如实空手。
    相似度阈值 0.55：sultans_game→sultan's_game≈0.97 必中；
    father→other 之类完全不像的词不会被硬凑。
    """
    import difflib

    out: list[str] = []
    for t in tags:
        idx = await _tbib_tag_index(t)
        if any(n == t for n, _c in idx):
            out.append(t)
            continue
        prefix = t
        best, best_ratio = None, 0.0
        # 全层级扫描到底取全局最优——不能在中间层提前收手：
        # sultans_game 在 "sultans" 层会撞上相似度刚过线的 sultanshade，
        # 而正确答案 sultan's_game 在再短一层 "sultan" 的候选里。
        while len(prefix) >= 4:
            for n, _c in await _tbib_tag_index(prefix):
                r = difflib.SequenceMatcher(None, t, n).ratio()
                if r > best_ratio:
                    best, best_ratio = n, r
            prefix = prefix[:-1]
        out.append(best if best is not None and best_ratio >= 0.55 else t)
    return out


# —— 多图源：寂寞随机图 API（国内可达，图库杂、题材类型更广） ——
# Lolicon 图库以女性向插画为绝对主体、无性别筛选参数；jitsu 是混合抓取
# 图库，题材构成更多样。仅私聊纯随机抽图时使用，带关键词搜索仍走
# Lolicon（只有它有标签检索）。群聊路径绝不触碰本图源。
JITSU_API = "https://moe.jitsu.top/img/"


async def fetch_jitsu_bytes(r18: bool = False) -> bytes | None:
    """直出图字节。失败返回 None，由调用方回落 Lolicon，绝不抛错。"""
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(
                JITSU_API,
                params={"r18": "1" if r18 else "false"},
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                if resp.status != 200:
                    return None
                data = await resp.read()
                # 太小的"图"多半是错误页，当失败处理
                if len(data) < 1024:
                    return None
                return data
    except Exception:
        return None


async def fetch_lolicon(r18: int = 0, tags: list[str] | None = None):
    """返回 ({size: 图片直链}, 是否R18)，失败返回 None。tags 为 pixiv 标签搜索词。"""
    # 请求 regular（约1200px），再按 pixiv 图床规则构造出 small（540px）做竞速
    params = {"num": 1, "r18": r18, "size": "regular"}
    if tags:
        params["tag"] = "|".join(tags)
    if TOKEN:
        params["token"] = TOKEN
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(
                "https://api.lolicon.app/setu/v2",
                params=params,
                timeout=aiohttp.ClientTimeout(total=8),
            ) as resp:
                data = await resp.json()
                if data.get("error"):
                    return None
                arr = data.get("data") or []
                if not arr:
                    return None
                d = arr[0]
                urls = d.get("urls") or {}
                url = urls.get("regular") or urls.get("original") or ""
                if not url:
                    return None
                picked = {"regular": url}
                if "i.pixiv.re/" in url:
                    small = url.replace("i.pixiv.re/", "i.pixiv.re/c/540x540_70/")
                    picked["small"] = small
                is_r18 = bool(d.get("r18"))
                # 上游字段偶尔漏填，用标签再兜一次
                if not is_r18:
                    tags = " ".join(d.get("tags") or []).lower()
                    is_r18 = ("r-18" in tags) or ("r18" in tags)
                return (picked, is_r18)
    except Exception:
        return None


async def fetch_image_bytes(urls: dict) -> bytes | None:
    """regular 和 small 同时下载：大图先到就发大图，否则发先到的小图。"""
    tasks = {
        asyncio.create_task(download_image(u)): k for k, u in urls.items() if u
    }
    if not tasks:
        return None
    done, pending = await asyncio.wait(
        tasks, timeout=8, return_when=asyncio.FIRST_COMPLETED
    )
    if not done:
        for t in pending:
            t.cancel()
        return None
    # 有小图先落地的话，最多再给大图 4 秒，到点就用小图
    got_small = None
    for t in done:
        img = t.result()
        if img and tasks[t] == "small":
            got_small = img
        elif img and tasks[t] == "regular":
            for p in pending:
                p.cancel()
            return img
    if got_small and pending:
        try:
            r_img = await asyncio.wait_for(
                asyncio.shield(list(pending)[0]), timeout=4
            )
            if r_img:
                return r_img
        except Exception:
            pass
    return got_small


# ============ Safebooru 扩展图库（AI 翻译标签） ============
# 二次元图库只有 pixiv 一个时，冷门词查不到；Safebooru 标签库更大，
# 但认英文标签。中文关键词先用 AI 翻译成图库标签再去查。

AI_KEY = os.getenv("OPENAI_API_KEY", "")
AI_URL = os.getenv("OPENAI_BASE_URL", "https://api.siliconflow.cn/v1")
AI_MODEL = os.getenv("OPENAI_MODEL", "Qwen/Qwen2.5-7B-Instruct")
_TAG_CACHE: dict[str, str] = {}


# ---------- 智能搜词链（2026-11-12 22:40 定版，替代"发现一个写一个"的映射法） ----------
# 流程：中文词 → AI 出 ≤3 个朴素英文候选词（不要求是标签）→ 逐个到 tbib
# 自动补全目录做"词元边界匹配"对齐成真实标签 → 按 explicit 实际库存排序。
# 要点：不信任 AI 的具体用词（奶奶翻成 granny/grandma/grandmother 任何一个
# 都能落到真标签上）；不信任标签总库存（只认 R18 实际库存）；词元黑名单
# （son/boy 等）把族系复合标签的未成年风险挡在红线外。
_CAND_CACHE: dict[str, list[str]] = {}
_CAND_PROMPT = (
    "你把中文搜索词翻译成二次元图库的英文检索词。"
    "只输出英文，最多3个不同说法的候选，用逗号分隔，全小写，"
    "用最朴素的常见英文单词或词组，不要自造复合词，不要解释。"
)


async def _ai_post(payload: dict, what: str) -> str:
    """调 AI 接口统一入口：20 秒超时 + 429 限流递增退避重试(最多4次) + 必打日志。
    （2026-11-12 实锤：X10 到智谱偶发读超时 + 晚高峰 429 限流实测 3拒1成，
    原 10 秒超时+静默吞异常导致翻译链无声死亡，用户搜"奶奶"只见搜空文案
    毫无排查线索——坑93 重演。成功结果有缓存，重试只发生在首次。）"""
    for i in range(4):
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.post(
                    f"{AI_URL}/chat/completions",
                    headers={"Authorization": f"Bearer {AI_KEY}"},
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as resp:
                    if resp.status == 429:
                        logger.warning(
                            f"[搜图]AI限流429({what})第{i + 1}次,退避重试"
                        )
                        await asyncio.sleep(3 + 3 * i)
                        continue
                    data = await resp.json(content_type=None)
                return str(data["choices"][0]["message"]["content"]).strip()
        except Exception as e:
            logger.warning(
                f"[搜图]AI调用失败({what})第{i + 1}次: {type(e).__name__} {e}"
            )
            await asyncio.sleep(2)
    return ""


async def _translate_candidates(query: str) -> list[str]:
    """中文词 → ≤3 个朴素英文候选词。失败返回 []，绝不抛错。"""
    if query in _CAND_CACHE:
        return _CAND_CACHE[query]
    raw = await _ai_post(
        {
            "model": AI_MODEL,
            "max_tokens": 60,
            "temperature": 0,
            # glm-4.7-flash+ 默认开深度思考，会把正文吃空——显式关闭
            "thinking": {"type": "disabled"},
            "messages": [
                {"role": "system", "content": _CAND_PROMPT},
                {"role": "user", "content": query},
            ],
        },
        "候选词",
    )
    if not raw:
        return []
    cands = [t.strip().strip('"').lower() for t in raw.splitlines()[0].split(",")]
    cands = [c for c in cands if c]
    if cands:
        _CAND_CACHE[query] = cands
    return cands


# 词元黑名单：族系复合标签（xx_and_son 之类）可能带出未成年向内容——红线
_TAG_PART_BLOCK = {"son", "grandson", "boy", "child", "kid", "loli", "shota",
                   "teen", "young", "brother"}


async def _tag_candidates_for(w: str) -> list[str]:
    """候选词 → 图库真实标签 ≤2 个（按标签总库存降序）。
    全词精确命中（库存≥3）直接用；否则全前缀探索目录 + 词元边界匹配
    （标签的语义单元必须含候选词本身，排除 grandia/grandpaced 这类
    同前缀杂讯）+ 词元黑名单。图库目录为准，不信 AI 用词。"""
    import difflib
    w = w.strip().lower().replace(" ", "_")
    if not w or len(w) < 3:
        return []
    for name, cnt in await _tbib_tag_index(w):
        if name == w and cnt >= 3:
            return [name]
    best: dict[str, int] = {}
    prefix = w[:-1] if len(w) > 5 else w
    while len(prefix) >= 4:
        for name, cnt in await _tbib_tag_index(prefix):
            if cnt < 3 or not name.startswith(prefix):
                continue
            parts = name.split("_")
            if w not in parts and not name.startswith(w + "_") and not name.endswith("_" + w):
                continue
            if any(p in _TAG_PART_BLOCK for p in parts):
                continue
            if difflib.SequenceMatcher(None, w, name).ratio() >= 0.6:
                best[name] = max(best.get(name, 0), cnt)
        prefix = prefix[:-1]
    return [n for n, _c in sorted(best.items(), key=lambda kv: -kv[1])[:2]]


_EXPLICIT_CNT: dict[str, int] = {}


async def _rank_by_explicit(tags: list[str]) -> list[str]:
    """按 explicit 实际库存降序，零库存剔除——标签总数会骗人
    （grandpa_gohan 总量 54 但 explicit 0），R18 库存不会。"""
    import re as _re
    scored: list[tuple[int, str]] = []
    for t in tags:
        if t in _EXPLICIT_CNT:
            c = _EXPLICIT_CNT[t]
        else:
            c = 0
            try:
                async with aiohttp.ClientSession() as sess:
                    async with sess.get(
                        f"{TBIB_API}?page=dapi&s=post&q=index&limit=1"
                        f"&tags=rating:explicit+{t}",
                        timeout=aiohttp.ClientTimeout(total=15),
                        headers={"User-Agent": _TBIB_UA},
                    ) as resp:
                        if resp.status == 200:
                            m = _re.search(r'count="(\d+)"', await resp.text())
                            c = int(m.group(1)) if m else 0
            except Exception:
                c = 0
            _EXPLICIT_CNT[t] = c
        if c > 0:
            scored.append((c, t))
    scored.sort(reverse=True)
    return [t for _c, t in scored]


async def _search_tag_candidates(query: str) -> list[str]:
    """中文词 → 图库真实标签列表（explicit 库存降序）。智能搜词链主入口。"""
    tags: list[str] = []
    for w in await _translate_candidates(query):
        for t in await _tag_candidates_for(w):
            if t not in tags:
                tags.append(t)
    if not tags:
        return []
    return await _rank_by_explicit(tags[:6])


_TRANSLATE_PROMPT = (
    "你把中文关键词翻译成 Danbooru/Safebooru 二次元图库的英文标签。"
    "规则：标签全小写、单词间用下划线，多个标签之间用逗号分隔，"
    "角色名用 名字_(作品名) 格式。只输出标签，不要解释。\n"
    "重要——必须使用图库真实存在的标签，禁止自造复合标签：\n"
    "1. 人物属性要拆开：外貌用 silver_hair/blonde/twintails 等独立标签，"
    "人数用 1girl/2girls/1boy/2boys，服饰用 maid/kimono/bikini 等\n"
    "2. 例：银发少女 → silver_hair, 1girl（不是 silver_hair_girl）\n"
    "3. 例：两个女仆 → maid, 2girls（不是 two_maids）\n"
    "常见对照：原神→genshin_impact；雷电将军→raiden_shogun；"
    "甘雨→ganyu；胡桃→hu_tao；初音未来→hatsune_miku；"
    "芙宁娜→furina；纳西妲→nahida；钟离→zhongli\n"
    "4. 泛指人物词（不是具体某人）→ 翻成性别+年龄+体格等属性标签组合，"
    "用图库真实存在的属性词，禁止亲属称谓直译（father/dad/mother/aunt "
    "这类词图库里无人用作标签）：\n"
    "   爸爸/大叔/熟男 → old_man 或 ojisan, male_focus；"
    "美男/帅哥 → bishounen 或 1boy, male_focus；"
    "姨/熟女/御姐 → milf, 1girl；肌肉男 → muscular_male, male_focus\n"
    "示例：苏丹的游戏 阿萨尔 → sultan's_game, azar_(sultan's_game)"
)


async def translate_tags(query: str) -> str:
    """中文关键词 → 图库英文标签，结果缓存。失败返回空串。"""
    if query in _TAG_CACHE:
        return _TAG_CACHE[query]
    raw = await _ai_post(
        {
            "model": AI_MODEL,
            "max_tokens": 60,
            "temperature": 0,
            "thinking": {"type": "disabled"},
            "messages": [
                {"role": "system", "content": _TRANSLATE_PROMPT},
                {"role": "user", "content": query},
            ],
        },
        "标签翻译",
    )
    if not raw:
        return ""
    tags = raw.splitlines()[0].strip().strip('"').lower()
    if tags:
        _TAG_CACHE[query] = tags
    return tags


async def fetch_safebooru(tags: str) -> str:
    """查 Safebooru（全年龄二次元图库），随机返回一张图的直链。失败返回空串。"""
    if not tags:
        return ""
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(
                "https://safebooru.org/index.php",
                params={
                    "page": "dapi",
                    "s": "post",
                    "q": "index",
                    "tags": tags,
                    "limit": 100,
                    "json": 1,
                },
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=aiohttp.ClientTimeout(total=8),
            ) as resp:
                arr = await resp.json(content_type=None)
                if not arr:
                    return ""
                import random as _r

                post = _r.choice(arr)
                return post.get("file_url") or ""
    except Exception:
        return ""


async def download_image(url: str) -> bytes | None:
    """把图拉回来：pixiv 图床带 Referer，其余站点带通用 UA，失败自动重试。"""
    headers = {
        "Referer": "https://www.pixiv.net/",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        ),
    }
    for _ in range(3):
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.get(
                    url, headers=headers, timeout=aiohttp.ClientTimeout(total=12)
                ) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.read()
                    if data and len(data) > 1024:
                        return data
        except Exception:
            pass
        await asyncio.sleep(0.3)
    return None


async def fetch_random_img() -> str:
    api = random.choice(RANDOM_IMG_APIS)
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(api, timeout=aiohttp.ClientTimeout(total=12)) as resp:
                data = await resp.json()
                return (
                    data.get("imgurl")
                    or data.get("img_url")
                    or data.get("image_url")
                    or ""
                )
    except Exception:
        return ""