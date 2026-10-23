"""从 Project Gutenberg 抓中文书目，生成本地目录 bot/data/gutenberg_zh.json

只在需要更新时才跑（Gutenberg 中文书目很少变动）。平时机器人读本地文件，
不联网也能匹配书名。

Gutenberg 的标题全是繁体（紅樓夢、山海經），用户多半敲简体，
所以这里顺手把简体版一起写进去。运行时就不必依赖 opencc 了。

同时合并简繁重复
----------------
Gutenberg 上同一本书常有两条记录，一条繁体标题一条简体（《二刻拍案惊奇》24162
和《二刻拍案驚奇》26729），或者两个不同版本（《閒情偶寄》25380 和 25471）。
按"归一化后的简体标题"合成一组，编号合并保留，下载时按顺序试。
用户只看到一条，不会因为敲简体还是繁体结果不一样。

用法：
    pip install opencc-python-reimplemented
    python3 scripts/fetch_gutenberg.py
"""
import asyncio
import json
import re
import sys
from pathlib import Path

import aiohttp

URL = "https://www.gutenberg.org/browse/languages/zh"
OUT = Path(__file__).resolve().parent.parent / "bot" / "data" / "gutenberg_zh.json"

# 抓 <li class="pgdbetext"> 和 <li class="pgdbaudio"> 两种
ROW = r'<li class="(pgdbetext|pgdbaudio)"><a href="/ebooks/(\d+)">([^<]+)</a>'


def norm(t: str) -> str:
    """归一化，只为了判断"是不是同一本书"。削括号版本信息、标点、大小写。"""
    t = re.sub(r"[（(\[【][^)）\]】]*[)）\]】]", "", t or "")
    return re.sub(r"[\s·・,，。.:：;；!！?？\"'“”‘’《》\-_/]+", "", t.lower())


# Gutenberg 的书名和中文读者习惯叫法有出入的，补上常用名。
# 编号是从 browse/languages/zh 页面里抄的，万一哪天 Gutenberg 改编号，
# 脚本会打警告，不会静默失效。
EXTRA_NAMES = {
    # 英文标题的中国典籍
    54567: "二十年目睹之怪现状",
    54820: "英人略述",          # 冷门小册子，留着能搜到就行
    49965: "道德经",
    27016: "洞天福地记",
    2090: "桃花源记",
    38585: "内功研究",
    4094: "论语",
    20968: "唐诗三百首",
    38580: "真心",
    27087: "五德集",
    # 书名对不上大众叫法的
    23950: "三国演义",          # Gutenberg 叫《三國志演義》
    25606: "三国志",            # 同上，避免和演义撞
}


async def main():
    try:
        import opencc
    except ImportError:
        print("缺 opencc：pip install opencc-python-reimplemented")
        return 1
    cc = opencc.OpenCC("t2s")

    async with aiohttp.ClientSession(headers={"User-Agent": "Mozilla/5.0"}) as s:
        async with s.get(URL, timeout=aiohttp.ClientTimeout(total=90)) as r:
            html = await r.text()

    rows = re.findall(ROW, html)
    if not rows:
        print("❌ 一条都没抓到，页面结构可能变了")
        return 1

    groups = {}
    for kind, bid, title in rows:
        title = title.strip()
        if not title:
            continue
        s = cc.convert(title)
        key = norm(s)
        if not key:
            continue
        g = groups.setdefault(key, {"title": title, "s": s, "ids": [], "alias": []})
        # aliases 收全组所有原始标题。合并后只留一个 title 会出事：
        # 《二刻拍案惊奇》和《二刻拍案驚奇》合成一条后，敲繁体那个就搜不到了。
        if title not in g["alias"]:
            g["alias"].append(title)
        if len(title) < len(g["title"]):
            g["title"], g["s"] = title, s
        if int(bid) not in g["ids"]:
            g["ids"].append(int(bid))

    books = {}
    merged = 0
    for key, g in groups.items():
        if len(g["ids"]) > 1:
            merged += len(g["ids"]) - 1
        g["ids"].sort()
        entry = {"ids": g["ids"], "s": g["s"]}
        # 只有真有别名时才写这个字段，省得目录里全是冗余，文件也能小一点
        if len(g["alias"]) > 1:
            entry["alias"] = sorted(g["alias"])
        books[g["title"]] = entry

    # Gutenberg 上有十本书用的是英文标题（"Three Hundred Tang Poems"、
    # "The Chinese Classics — Volume 1: Confucian Analects"），中文用户一辈子
    # 不会这么敲。这里按编号补上中文名，运行时就能搜到。
    for bid, extra in EXTRA_NAMES.items():
        for title, entry in books.items():
            if bid not in entry["ids"]:
                continue
            if extra not in entry.get("alias", []) and extra != title:
                entry.setdefault("alias", []).append(extra)
                entry["alias"].sort()
            break
        else:
            print(f"   ⚠️  {bid}（{extra}）不在目录里，可能已下架")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(books, ensure_ascii=False, indent=0, sort_keys=True),
        encoding="utf-8",
    )
    total_ids = sum(len(v["ids"]) for v in books.values())
    print(f"✅ 页面 {len(rows)} 条 → 合并重复 {merged} 条 → "
          f"{len(books)} 本书（共 {total_ids} 个版本）")
    print(f"   写入 {OUT}  ({OUT.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
