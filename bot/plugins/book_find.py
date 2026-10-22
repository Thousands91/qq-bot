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

为什么不支持现代书下载
----------------------
试过的都不可用：Anna's Archive / Z-Library / LibGen 全部连不上；微信读书、
京东读书、当当要登录态且从不提供整本文件；超星、读秀要机构账号。
现代书在版权期内，本来也没有合法的整本下载渠道。所以这部分只给豆瓣链接。
"""
import json
import os
import random
import re
from pathlib import Path
from typing import List

import aiohttp
from nonebot import on_command
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message, MessageSegment

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
GUTENBERG_TXT = "https://www.gutenberg.org/ebooks/{}.txt.utf-8"
GUTENBERG_CACHE = "https://www.gutenberg.org/cache/epub/{}/pg{}.txt"
CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "gutenberg_zh.json"
DL_MAX = 8 * 1024 * 1024      # 超过 8MB 不发，QQ 传大文件容易断
DL_TIMEOUT = 60
MAX_TRIES = 20        # 断流重试次数（每次能续上几十到几百 KB，大书要多试几轮）

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
async def _(event: GroupMessageEvent):
    raw = event.get_plaintext().strip()
    for p in ("/找书", "!找书", "！找书", "/淘书", "!淘书", "/找本书",
              "/有这本书吗", "!有这本书吗"):
        raw = raw.replace(p, "", 1)
    raw = raw.strip()

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
                f"\n{GUTENBERG_TXT.format(old['id'])}"
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

def load_catalog() -> dict:
    """读本地古籍目录。文件没了就返回空字典，不影响现代书查询。"""
    try:
        return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


CATALOG = load_catalog()


def match_old(keyword: str):
    """在古籍目录里找一本最像的。

    匹配放宽一点：先把书名里的标点削掉、把「的/之」这类虚词去掉，
    再比"关键字包含书名"或"书名包含关键字"，这样"下载红楼梦"也能中。
    """
    k = _norm(keyword)
    if not k:
        return None
    best = None
    best_score = 0
    for title, info in CATALOG.items():
        for cand in (title, info.get("s", "")):
            c = _norm(cand)
            if not c:
                continue
            if c == k:
                score = 100
            elif c in k:
                score = 60 + len(c)          # 书名越长越可信
            elif k in c and len(k) >= 2:
                score = 30 + len(k)
            else:
                continue
            if score > best_score:
                best_score = score
                best = {"title": info.get("s") or title, "origin": title,
                        "id": info["ids"][0]}
    return best


async def fetch_txt(book_id: int):
    """取一本古籍的纯文本，断了就续。

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
    """
    size = None
    for url in (GUTENBERG_CACHE.format(book_id, book_id),
                GUTENBERG_TXT.format(book_id)):
        data = b""
        for _ in range(MAX_TRIES):
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
                            data_done = True
                            break
                        if r.status not in (200, 206):
                            break
                        if r.status == 200 and data:
                            data = b""               # 服务端不肯续传，从头来
                        if size is None and r.status == 200:
                            size = int(r.headers.get("Content-Length") or 0)
                        async for chunk in r.content.iter_chunked(16 * 1024):
                            data += chunk
                            if len(data) > DL_MAX:
                                return None, "太大"
            except Exception:
                pass      # 断了不慌，下一轮接着要
            if len(data) >= DL_MAX:
                break
            # 拿够了就停：有 Content-Length 就按长度判断，没有就看结束标记
            if size and len(data) >= size:
                break
            if not size and b"END OF" in data[-2048:]:
                break

        # 完整性：长度对得上，或者有 Gutenberg 的结束标记。
        # 早先只认 "END OF"，结果像 12479 这种没有该标记的完整文件被误判成残缺。
        if len(data) < 512 or b"Project Gutenberg" not in data[:4000]:
            continue
        if size and len(data) < size * 0.99:
            continue
        return data, ""
    return None, "没取全"


async def send_txt(event: GroupMessageEvent, book: dict) -> bool:
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
