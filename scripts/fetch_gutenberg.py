"""从 Project Gutenberg 抓中文书目，生成本地目录 bot/data/gutenberg_zh.json

只在需要更新时才跑（Gutenberg 中文书目很少变动）。平时机器人读本地文件，
不联网也能匹配书名。

Gutenberg 的标题全是繁体（紅樓夢、山海經），用户多半敲简体，
所以这里顺手把简体版一起写进去。运行时就不必依赖 opencc 了。

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


async def main():
    try:
        import opencc
    except ImportError:
        print("缺 opencc：pip install opencc-python-reimplemented")
        return 1
    cc = opencc.OpenCC("t2s")

    async with aiohttp.ClientSession(headers={"User-Agent": "Mozilla/5.0"}) as s:
        async with s.get(URL, timeout=aiohttp.ClientTimeout(total=60)) as r:
            html = await r.text()

    rows = re.findall(
        r'<li class="pgdbetext"><a href="/ebooks/(\d+)">([^<]+)</a>', html
    )
    books = {}
    for bid, title in rows:
        title = title.strip()
        if not title:
            continue
        item = books.setdefault(title, {"ids": [], "s": cc.convert(title)})
        if int(bid) not in item["ids"]:
            item["ids"].append(int(bid))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(books, ensure_ascii=False, indent=0, sort_keys=True),
        encoding="utf-8",
    )
    print(f"✅ 抓到 {len(rows)} 条，去重后 {len(books)} 本")
    print(f"   写入 {OUT}  ({OUT.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
