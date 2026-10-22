"""实测下载：直接在插件源码上跑，验证 Content-Length 判据能否拦住截断

之前的现象：
  红楼梦 官方 2663455 字节，只下到 502935 就"正常结束"，被判为完整
这脚本专门盯这件事。
"""
import asyncio
import re
import time
from pathlib import Path

import aiohttp

SRC = Path("/workspace/qq-bot-project/bot/plugins/book_find.py")

# 常量照抄插件里的值，别用正则去抓——多行元组会被截断
GUTENBERG_HOST = "https://www.gutenberg.org"
MIRROR_HOST = "https://gutenberg.pglaf.org"
MIRRORS = (GUTENBERG_HOST, MIRROR_HOST)
DL_MAX = 8 * 1024 * 1024
DL_TIMEOUT = 60
MAX_TRIES = 8
MAX_MIRROR_TRIES = 3
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


def grab(name: str) -> str:
    src = SRC.read_text(encoding="utf-8")
    m = re.search(rf'^(?:async )?def {re.escape(name)}\b.*?(?=\n(?:async )?def |\n# ---|\Z)',
                  src, re.S | re.M)
    if not m:
        raise SystemExit(f"找不到 {name}")
    return m.group(0)


NS = dict(globals())
for fn in ("mirror_path", "_urls", "_total_size", "_pull", "fetch_txt"):
    exec(grab(fn), NS)


async def main():
    fetch = NS["fetch_txt"]
    cases = [
        (12479, "三字經", 24224),      # 镜像上只有 4628 的残本，必须取官方
        (24264, "紅樓夢", 2663455),    # 之前只下到 502935 就断了
        (25376, "三俠五義", 1524 * 1024),
    ]
    for bid, name, expect in cases:
        t = time.time()
        data, err = await fetch(bid)
        dt = time.time() - t
        if data:
            head = data[:46].decode("utf-8", "ignore").replace("\n", " ")
            got = "✅" if len(data) >= expect * 0.95 else "⚠️ "
            print(f"{got} {name} {len(data)}B 期望≈{expect} {dt:5.1f}s  {head}")
        else:
            print(f"❌ {name} 失败：{err}  {dt:.1f}s")


asyncio.run(main())
