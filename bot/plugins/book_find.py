"""
找书 —— 阿萨尔的书店

群里发 /找书 三体        → 阿萨尔报几本书，附作者年份和豆瓣链接
群里发 /找书 山海经 下载  → 若是公有领域的古籍，直接把 txt 发进群

为什么要做这个
-------------
阿萨尔是开书店的，他的毕生志业是"编纂百科全书、只写亲眼见过的事"。
"帮他找一本书"是他本行里最自然的一件事，比抽签、点歌都更贴。

数据源分两半
------------
**现代书** 走豆瓣 subject_suggest（无需 key），返回 title / author_name /
year / url，搜不到就是空数组。详情接口（简介、评分）全要 key 或已下线，
所以卡片里只有书名、作者、年份、链接四样。

**古籍** 走 Project Gutenberg。它的中文区有 409 本，全部是公有领域作品
（四大名著、《山海經》《三字經》《老殘遊記》…），可以合法下载 txt 进群。
目录已抓成本地文件 bot/data/gutenberg_zh.json，所以匹配书名不联网也行。
官方站连不上时自动降级到 pglaf 镜像（见 MIRRORS）。

为什么不支持现代书下载
----------------------
试过的都不可用：Anna's Archive / Z-Library / LibGen 全部连不上；微信读书、
京东读书、当当要登录态且从不提供整本文件；超星、读秀要机构账号。
现代书在版权期内，本来也没有合法的整本下载渠道。所以这部分只给豆瓣链接
和微信读书的试读入口，让人自己去读前面几章。

维基文库和 ctext 为什么没接
---------------------------
zh.wikisource.org 及全部镜像、ctext.org 在实测网络里 DNS 能解析但 TCP 直连超时，
站点本身被阻断，不是代码问题。dumps.wikimedia.org 虽然能连，但中文维基文库里
最有价值的现代标点校勘本仍在版权内，整包 dump 有 9.5GB，塞不进手机。
所以古籍这条线仍然只靠 Gutenberg。哪天网络条件变了，在 MIRRORS 里加一条就行。
"""
import json
import os
import random
import re
from pathlib import Path
from typing import List

import aiohttp
from nonebot import on_command
from nonebot.adapters.onebot.v11 import GroupMessageEvent, PrivateMessageEvent, Message, MessageSegment
from nonebot.params import CommandArg

find_cmd = on_command(
    "找书", aliases={"淘书", "找本书", "有这本书吗"}, priority=20, block=True
)

SEARCH = "https://book.douban.com/j/subject_suggest"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
REFERER = "https://book.douban.com/"

MAX_BYTES = 256 * 1024
WANT = 3          # 报几本
MAX_TITLE = 32    # 书名过长就截断，免得撑破消息

# ---- 古籍下载 ----
GUTENBERG_HOST = "https://www.gutenberg.org"
MIRROR_HOST = "https://gutenberg.pglaf.org"

# 官方站最近频繁连不上（实测 300KB 要 27 秒，还常断在几十 KB），
# pglaf 是 Gutenberg 的官方镜像站，结构更老但稳得多。两个都试，谁先给全用谁。
# 顺序有讲究：先官方——它的 txt 是 utf-8 编码，镜像里有些老书是 Latin-1。
MIRRORS = (GUTENBERG_HOST, MIRROR_HOST)

CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "gutenberg_zh.json"
DL_MAX = 8 * 1024 * 1024      # 超过 8MB 不发，QQ 传大文件容易断
DL_TIMEOUT = 60
MAX_TRIES = 8         # 每个域名最多续传几轮，两个域名加起来 16 轮，够把 1MB 拖完
MAX_MIRROR_TRIES = 3  # 镜像站很少断，不用给那么多轮

API_KEY = os.getenv("OPENAI_API_KEY", "")
BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.siliconflow.cn/v1")
MODEL = os.getenv("OPENAI_MODEL", "Qwen/Qwen2.5-7B-Instruct")

# 没有 AI 时的固定台词。按"找到 / 没找到"分两拨，随机取，避免回回一样。
FOUND_LINES = [
    "这几本我柜上都有印象，您挑一本。",
    "都在脑子里，我给您报个名目。",
    "这几本，我见过。",
    "翻出来了，您看是哪一版。",
]
MISS_LINES = [
    "这个名目，我这儿没有记载。",
    "翻遍了，没有这一本。是我孤陋了。",
    "没见过这本书。若真有，我倒是想看看。",
    "柜上没有。您再说得细些？",
]
DL_LINES = [
    "这一本我柜上有，给您。",
    "翻出来了，纸是旧的，字还清楚。",
    "拿去。看完了别还。",
]


@find_cmd.handle()
async def _(event: GroupMessageEvent | PrivateMessageEvent, arg: Message = CommandArg()):
    # 前缀可能为空串（"找书"裸词就能触发），此时 get_plaintext() 里没有
    # "/找书" 可替换，整句会被当成书名。参数交给 CommandArg 出。
    raw = arg.extract_plain_text().strip()

    # "山海经 下载" / "下载 红楼梦" 都行
    want_dl = False
    for w in ("下载", "发我", "发一份", "传我", "txt", "TXT"):
        if w in raw:
            want_dl = True
            raw = raw.replace(w, " ")
    kw = re.sub(r"\s+", " ", raw).strip()

    if not kw:
        await find_cmd.finish("报个书名，或者作者、一句话情节也行。")

    # 古籍先查：目录在本地，比豆瓣快，也不用联网
    old = match_old(kw)
    if old:
        if want_dl:
            await find_cmd.send("柜子深处那格，我找找……")
            ok = await send_txt(event, old)
            if ok:
                return
            await find_cmd.finish(
                f"《{old['title']}》那本取不下来——Gutenberg 那边没应声。"
                f"\n{GUTENBERG_HOST}/ebooks/{old['id']}"
            )
        # 没说要下载，就别自作主张发文件，只提一句
        await find_cmd.finish(
            f"《{old['title']}》——这一本我柜上有全文，说声「下载」我就给您。"
        )

    if want_dl:
        # 现代书：先说清楚没有整本，再照常报书目，别让人空手走。
        # 这句的措辞别和 FOUND_LINES 撞——早先前缀和开场白都带"报个名目"，
        # 连着发两句就像口吃。
        await find_cmd.send(
            f"「{kw}」——现代的印本我这儿没有能整本递出去的本子。"
            f"不过名目还是有的："
        )

    books = await search(kw)
    if not books:
        await find_cmd.finish(f"「{kw}」——{random.choice(MISS_LINES)}")

    books = books[:WANT]
    head = await remark(kw, books)
    lines = [head, ""]

    # 每本书报"作者 + 年份 + 豆瓣页"，再在末尾按平台给一排链接。
    # 不给每本书配四个平台的链接：三本书乘四个平台就是十二条，
    # 群里一屏都装不下，而且同一个人在哪个平台买，跟具体是哪本关系不大。
    for i, b in enumerate(books, 1):
        author = b["author"] or "佚名"
        year = f"（{b['year']}）" if b["year"] else ""
        lines.append(f"{i}. {b['title']}　{author}{year}")
        lines.append(f"　　{b['url']}")

    # 试读：微信读书对绝大多数在版书开放前几章免费。这里只给"去读"的入口，
    # 不假装我们能替人把整本弄下来——那件事做不成，说清楚比糊弄强。
    lines.append("")
    lines.append("想先翻两页的，微信读书多半能试读：")
    lines.append(f"　https://weread.qq.com/web/search/books?keyword={kw}")

    lines.append("")
    lines.append("要去别处看看，往这儿走：")
    for name, url in platforms(kw):
        lines.append(f"　{name}　{url}")

    await find_cmd.finish(Message("\n".join(lines)))


# 各平台按"搜书名"的地址。都是实测过的：
# - 豆瓣 subject_search 是网页搜索，能直接出书；不用那个只返 JSON 的建议接口
# - 微信读书 / QQ 阅读的搜索页是 JS 渲染，但地址有效，点开就出结果
# - 京东、当当、孔夫子都走搜索页，不硬编码某个商品的 id（会变）
# - 关键字**不做 percent-encode**：QQ 里 %E4%B8%89%E4%BD%93 这种一眼看不懂，
#   而各站都认原样的中文（实测微信读书 329 处命中、QQ阅读 49 处）。
def platforms(keyword: str) -> list:
    return [
        ("微信读书", f"https://weread.qq.com/web/search/books?keyword={keyword}"),
        ("QQ阅读", f"https://book.qq.com/so/{keyword}"),
        ("京东", f"https://search.jd.com/Search?keyword={keyword}&enc=utf-8"),
        ("当当", f"https://search.dangdang.com/?key={keyword}"),
        ("孔夫子旧书", f"https://search.kongfz.com/product/?keyword={keyword}"),
        ("喜马拉雅", f"https://www.ximalaya.com/search/{keyword}"),
    ]


# ---------------------------------------------------------------- 古籍

# 判断标题里有没有汉字。Gutenberg 有十来本用英文标题的中国典籍，排序时要让位给中文原文。
_HAS_CJK = re.compile(r"[\u4e00-\u9fff]")


# 简繁对照：运行时不装 opencc（20MB 的包，手机不必要），
# 用这张表覆盖目录里出现过的繁体字，198 个字，够用。
# 重新生成：python3 scripts/gen_t2s.py
_T2S_FROM = (
    "俠備傳傷傾僉兒冊別剛劍勝叢吳吶國圍園圖團報場壇壺壽夢妝嬌孫學宮將尋島師庫廂廣張後"
    "恆憶戲斬斷書東棄楊樂樓歐歡歸殘殺淵滄滬滸滿漢灣無燈爐爾牘狀現瑣瓊甌畫異癡禪禮竇筆"
    "箋紀約紅經綠緣編織繚繡續羅義習翹聖聞聯聲臺舊莊華葉蓮蕩蕭蘇蘭補製見規覽觀訓記訪註"
    "詞詠詩話語說誼調談論諧諫證譚讀變豐豔貞負賀賈賦載轟遊選遺鄧鄭鄰錄錦鍾鏡鐘鐵鐸鑒長"
    "開閒間閣閨閱關陽際隨雙雜雞離雲韓韜頭顔顯風飛飲餘馬駐駢騙驚魚鳳鴻鶯鹽黃點齋龍"
)
_T2S_TO = (
    "侠备传伤倾佥儿册别刚剑胜丛吴呐国围园图团报场坛壶寿梦妆娇孙学宫将寻岛师库厢广张后"
    "恒忆戏斩断书东弃杨乐楼欧欢归残杀渊沧沪浒满汉湾无灯炉尔牍状现琐琼瓯画异痴禅礼窦笔"
    "笺纪约红经绿缘编织缭绣续罗义习翘圣闻联声台旧庄华叶莲荡萧苏兰补制见规览观训记访注"
    "词咏诗话语说谊调谈论谐谏证谭读变丰艳贞负贺贾赋载轰游选遗邓郑邻录锦钟镜钟铁铎鉴长"
    "开闲间阁闺阅关阳际随双杂鸡离云韩韬头颜显风飞饮余马驻骈骗惊鱼凤鸿莺盐黄点斋龙"
)
_T2S = str.maketrans(_T2S_FROM, _T2S_TO)


def _t2s(t: str) -> str:
    """繁体转简体，只为让书名比对能通。表里没有的字原样保留。"""
    return (t or "").translate(_T2S)


def load_catalog() -> dict:
    """读本地古籍目录。文件没了就返回空字典，不影响现代书查询。"""
    try:
        return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


CATALOG = load_catalog()


def match_old(keyword: str):
    """在古籍目录里找一本最像的。

    匹配放宽一点：先把书名里的标点削掉，再比"关键字包含书名"或"书名包含关键字"，
    这样"下载红楼梦"也能中。

    每个条目要比三种写法：条目标题（繁体原题）、s（简体）、alias（组内其它写法）。
    alias 不能省——《二刻拍案惊奇》和《二刻拍案驚奇》在 Gutenberg 上是两条记录，
    目录合并成一条后，不把别名一起比，敲繁体那个名字的人就搜不到了。

    同分时中文优先
    --------------
    搜"论语"会同时命中中文原文《論語》(23839) 和英文译本
    "The Chinese Classics — Volume 1: Confucian Analects"(4094)，两者都算精确匹配。
    这不是理论问题，是实际排序问题：给中文群发一本英文书毫无道理。
    所以纯英文标题的条目在同分时让位。

    关键字也要转一遍
    ----------------
    目录里同时存了繁体原题和简体名，但 `_norm` 只做标点清理、不做简繁转换。
    用户敲"三國演義"（繁），条目里只有"三国演义"（简），对不上——
    所以比较前先把关键字转成简体。运行时不能依赖 opencc（那是 20MB 的包，
    手机装不下也没必要），这里用一张常用字表，覆盖书名里出现的那几百个字。
    """
    k = _norm(keyword)
    if not k:
        return None
    k_s = _norm(_t2s(keyword))
    hits = []
    for title, info in CATALOG.items():
        cands = [title, info.get("s", "")] + list(info.get("alias") or [])
        best_local = 0
        for cand in cands:
            c = _norm(cand)
            if not c:
                continue
            # 繁体和简体两个方向都试：条目可能存繁体，用户可能敲简体，反之亦然
            for q, cc in ((k, c), (k_s, _norm(_t2s(cand)))):
                if not q:
                    continue
                if cc == q:
                    score = 100
                elif cc in q:
                    score = 60 + len(cc)     # 书名越长越可信
                elif q in cc and len(q) >= 2:
                    score = 30 + len(q)
                else:
                    continue
                best_local = max(best_local, score)
        if not best_local:
            continue
        # 纯英文标题垫后；同分时先到先得，保持目录顺序稳定
        is_en = not _HAS_CJK.search(title)
        hits.append((best_local - (5 if is_en else 0), len(title), title, info))

    if not hits:
        return None
    # 分数高的在前；同分选标题短的（《論語》优于《論語注疏》）
    hits.sort(key=lambda h: (-h[0], h[1]))
    _, _, title, info = hits[0]
    return {"title": info.get("s") or title, "origin": title, "id": info["ids"][0]}


async def fetch_txt(book_id: int):
    """取一本古籍的纯文本，断了就续，官方站不行就换镜像。

    这个下载链路有两个坑，都得绕：

    1. **gzip 会骗 Content-Length。** Gutenberg 回 Content-Encoding: gzip，
       压缩后 48775 字节，解压后却是 141KB——aiohttp 拿这个长度一对就对不上，
       直接抛 ClientPayloadError。所以要显式要 identity，别让它压缩。

    2. **连着传一会儿会断。** 沙箱到 Gutenberg 这条路很慢（300KB 要 27 秒），
       传到一两百 KB 常常被掐。于是按 Range 续传：断了记住已读多少，
       下一次从那个字节接着要，最多试 MAX_TRIES 次。每次只信自己数到的字节，
       不依赖 Content-Length 是否准确。

    最后还要查结尾有没有 "*** END OF"——有头没尾的半截本子发到群里，
    比不发更难受。

    镜像的坑单独说
    --------------
    pglaf 镜像是**旧快照**，有几本书停在很老的修订上。实测《三字經》(12479)
    官方 24KB，镜像只有 4.6KB——正文都在，但前言、注释、版权页全没了。
    所以镜像只能当降级用，宁可报"取不下来"也不能把残本递出去。
    完整性判断在 _pull 里，只认 Content-Length。
    """
    for host in MIRRORS:
        data, err = await _pull(host, book_id)
        if data:
            return data, ""
    return None, err if not err else "没取全"


def mirror_path(book_id: int) -> str:
    """算 pglaf 镜像里的目录。

    它用的是 Gutenberg 最老的那套布局：把 id 去掉前导零，**最后一位之前
    每位一层，末位单独成一级**。实测对照：

        24264 → 2/4/2/6/24264/
        12479 → 1/2/4/7/12479/
         7376 → 7/3/7/7376/
         2090 → 2/0/9/2090/     ← 只有三级，末级目录直接是 2090

    2090 这种四位 id 最容易搞错：2/0/9/0/ 下面装的是 20900-20909 那批，
    不是 2090。所以最后一位必须单独断开，不能跟前面的合并。
    """
    s = str(book_id).lstrip("0") or "0"
    return "/".join(list(s[:-1]) + [str(book_id)])


def _urls(host: str, book_id: int) -> list:
    """某个域名下，这本书可能在哪几个地址。挨个试，第一个能下的算数。"""
    if host == MIRROR_HOST:
        d = mirror_path(book_id)
        return [f"{host}/{d}/{book_id}-0.txt"]
    # 官方站：cache 路径最快最稳，ebooks 那个是跳转后的正式地址
    return [
        f"{host}/cache/epub/{book_id}/pg{book_id}.txt",
        f"{host}/ebooks/{book_id}.txt.utf-8",
    ]


async def _pull(host: str, book_id: int):
    """在一个域名下把整本书拖下来。成功返回 (bytes, "")，失败返回 (None, 原因)。

    判"拿全了"只认一个东西：**Content-Length**。这不是偷懒，是被坑出来的：

    - 用 "END OF" 判结尾不行。官方新版文件里这个标记在正文之后、捐款说明之前，
      离文件尾还有两千字节；镜像上的老版文件干脆没有这个标记。两头都不靠谱。
    - 用"读满 DL_TIMEOUT 秒没断就算完"也不行。实测官方站 红楼梦 是 2663455 字节，
      传到 502935 字节连接自己断了，`iter_chunked` 不抛异常就收尾，看起来像正常结束。

    所以第一次请求一定记下 Content-Length，之后每轮都拿 len(data) 跟它比。
    """
    tries = MAX_TRIES if host == GUTENBERG_HOST else MAX_MIRROR_TRIES
    for url in _urls(host, book_id):
        data = b""
        size = 0
        for _ in range(tries):
            try:
                headers = {"User-Agent": UA, "Accept-Encoding": "identity"}
                if data:
                    headers["Range"] = f"bytes={len(data)}-"
                async with aiohttp.ClientSession() as sess:
                    async with sess.get(
                        url,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=DL_TIMEOUT,
                                                      sock_read=45),
                    ) as r:
                        if r.status == 416:          # 要不到更多了，收工
                            break
                        if r.status not in (200, 206):
                            break
                        if r.status == 200 and data:
                            data = b""               # 服务端不肯续传，从头来
                        # Content-Range 形如 "bytes 100-999/2663455"，斜杠后才是总长
                        total = _total_size(r.headers)
                        if total:
                            size = total
                        async for chunk in r.content.iter_chunked(16 * 1024):
                            data += chunk
                            if len(data) > DL_MAX:
                                return None, "太大"
            except Exception:
                pass      # 断了不慌，下一轮接着要
            if len(data) >= DL_MAX:
                break
            if size and len(data) >= size:
                break

        if len(data) < 512 or b"Project Gutenberg" not in data[:4000]:
            continue
        # 知道总长就必须拿满；不知道总长（极少）才退回看 END 标记
        if size:
            if len(data) < size:
                continue
        elif not (b"*** END OF" in data or b"End of the Project Gutenberg" in data):
            continue
        return data, ""
    return None, "没取全"


def _total_size(headers) -> int:
    """从响应头里抠出文件总长度。Content-Length 和 Content-Range 都认。"""
    try:
        cr = headers.get("Content-Range") or ""
        if "/" in cr:
            tail = cr.rsplit("/", 1)[1].strip()
            if tail.isdigit():
                return int(tail)
        cl = headers.get("Content-Length")
        if cl and str(cl).isdigit():
            return int(cl)
    except Exception:
        pass
    return 0


async def send_txt(event: GroupMessageEvent | PrivateMessageEvent, book: dict) -> bool:
    """把 txt 发进群。成功返回 True。"""
    data, err = await fetch_txt(book["id"])
    if not data:
        return False
    # Gutenberg 的 txt 是 UTF-8，个别老书是 Latin-1，这里只保证不是乱码
    fname = f"{book['title']}.txt"
    try:
        await find_cmd.send(
            MessageSegment(
                "file",
                {"file": f"base64://{__import__('base64').b64encode(data).decode()}",
                 "name": fname},
            ),
            _timeout=60 + len(data) // (200 * 1024),
        )
    except BaseException:
        return False
    # 文件发完再补一句，别让群里只剩一个光秃秃的文件
    try:
        await find_cmd.send(
            f"{random.choice(DL_LINES)}\n"
            f"《{book['title']}》· 公有领域，Gutenberg 版"
        )
    except Exception:
        pass
    return True


# ---------------------------------------------------------------- 豆瓣

async def search(keyword: str) -> List[dict]:
    """查豆瓣，返回干净的书目列表。出错一律当"没找到"，不抛给用户。"""
    try:
        async with aiohttp.ClientSession(
            headers={"User-Agent": UA, "Referer": REFERER}
        ) as sess:
            async with sess.get(
                SEARCH,
                params={"q": keyword},
                timeout=aiohttp.ClientTimeout(total=12),
            ) as r:
                if r.status != 200:
                    return []
                raw = await r.content.read(MAX_BYTES)
        import json

        items = json.loads(raw.decode("utf-8", "ignore") or "[]")
    except Exception:
        return []

    out = []
    seen = set()
    for it in items if isinstance(items, list) else []:
        # type 为 b 才是书，其余是电影 / 音乐
        if it.get("type") != "b":
            continue
        title = (it.get("title") or "").strip()
        url = (it.get("url") or "").strip()
        if not title or not url:
            continue
        # 同一本书常有好几个版本（平装/精装/大字本），只留一条
        if _norm(title) in seen:
            continue
        seen.add(_norm(title))
        if len(title) > MAX_TITLE:
            title = title[:MAX_TITLE] + "…"
        author = re.sub(r"\s+", " ", (it.get("author_name") or "").strip())
        if len(author) > 24:
            author = author[:24] + "…"
        out.append({
            "title": title,
            "author": author,
            "year": (it.get("year") or "").strip(),
            "url": url,
        })
    return _rank(out, keyword)


def _norm(t: str) -> str:
    """书名归一化：只削掉括号里的版本信息（"（大字本）""(第2版)"），

    其余字符一律保留。早先连罗马数字一起删了，结果《三体Ⅱ》《三体Ⅲ》
    被当成《三体》的重复版本给并掉了。
    """
    t = re.sub(r"[（(\[【][^)）\]】]*[)）\]】]", "", t or "")
    return re.sub(r"[\s·・,，。.:：;；!！?？\"'“”‘’《》\-_/]+", "", t.lower())


def _rank(books: List[dict], keyword: str) -> List[dict]:
    """把最像用户想找的那本排前面。

    豆瓣按相关度给，但"余华长篇小说"这种合集会压过《活着》，群里看着别扭。
    规则很短：书名正好等于关键字 > 书名含关键字 > 作者署名含关键字 > 其余。
    """
    k = _norm(keyword)

    def score(b):
        n = _norm(b["title"])
        if n == k:
            return 0
        if k and k in n:
            return 1
        if k and k in _norm(b["author"]):
            return 2
        return 3

    return sorted(books, key=score)


async def remark(keyword: str, books: List[dict]) -> str:
    """阿萨尔说一句。有 AI 就让 AI 说，没有就用固定台词。"""
    if not API_KEY:
        return random.choice(FOUND_LINES)

    names = "、".join(f"《{b['title']}》" for b in books)
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)
        resp = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": (
                    "你是《苏丹的游戏》里的书店老板阿萨尔：智慧 4，记得住自己"
                    "读过的每一本书，毕生编纂一部只写亲眼所见之事的百科全书。"
                    "文雅、克制、书商口吻，自称我，称对方您。"
                    "只说一句话，不超过 30 字。不卖萌，不反问，不用颜文字，"
                    "不要提苏丹卡、七日、百科全书这些词。"
                )},
                {"role": "user", "content": (
                    f"有人来店里问「{keyword}」，你柜上翻出了{names}。"
                    "用一句话说给他，像书商递书那样。"
                    "这些书你确实见过，不要说'帮您查查'之类的话。"
                )},
            ],
            max_tokens=60,
            temperature=0.8,
        )
        text = (resp.choices[0].message.content or "").strip()
        text = re.sub(r"^[\"“「]|[\"”」]$", "", text)
        return text or random.choice(FOUND_LINES)
    except Exception:
        return random.choice(FOUND_LINES)
