"""
找书 —— 阿萨尔的书店

群里发 /找书 三体  → 阿萨尔翻柜子，报一本书，附作者年份和豆瓣链接

为什么要做这个
-------------
阿萨尔是开书店的，他的毕生志业是"编纂百科全书、只写亲眼见过的事"。
"帮他找一本书"是他本行里最自然的一件事，比抽签、点歌都更贴。

数据源
------
豆瓣的 subject_suggest 接口（无需 key）：
    https://book.douban.com/j/subject_suggest?q=三体
返回 title / author_name / year / url，搜不到就是空数组，比搜索引擎可靠。

详情接口（简介、评分）全要 key 或已下线，所以卡片里只有书名、作者、年份、
链接四样。够用了——群里没人会读完一段简介。

回复风格
--------
AI 有 key 时，让阿萨尔按人设说一句（他记得住读过的每一本书，所以语气是
"这书在我脑子里"而不是"我帮您查一下"）。没 key 就用固定台词，功能照常。
"""
import os
import random
import re
from typing import List

import aiohttp
from nonebot import on_command
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message

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


@find_cmd.handle()
async def _(event: GroupMessageEvent):
    kw = event.get_plaintext().strip()
    for p in ("/找书", "!找书", "！找书", "/淘书", "!淘书", "/找本书",
              "/有这本书吗", "!有这本书吗"):
        kw = kw.replace(p, "", 1)
    kw = kw.strip()

    if not kw:
        await find_cmd.finish("报个书名，或者作者、一句话情节也行。")

    books = await search(kw)
    if not books:
        await find_cmd.finish(f"「{kw}」——{random.choice(MISS_LINES)}")

    books = books[:WANT]
    head = await remark(kw, books)

    lines = [head, ""]
    for i, b in enumerate(books, 1):
        author = b["author"] or "佚名"
        year = f"（{b['year']}）" if b["year"] else ""
        lines.append(f"{i}. {b['title']}　{author}{year}")
        lines.append(f"　　{b['url']}")

    await find_cmd.finish(Message("\n".join(lines)))


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
