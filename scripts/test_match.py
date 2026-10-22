"""校验古籍匹配：从插件里摘函数跑，检查繁简双向命中与排序

这个脚本存在的理由：书名匹配全靠 _norm / _t2s / match_old 这三个函数，
它们互相咬合得紧，改一个就可能把另一个弄坏。之前就出过两次：
  1. 合并简繁重复后，敲繁体那个名字的人搜不到了
  2. 搜"论语"命中的是英文译本 4094，而不是中文原文 23839
所以每次改都跑一遍这里。

用法：
    python3 scripts/test_match.py
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "bot" / "plugins" / "book_find.py"
CAT = ROOT / "bot" / "data" / "gutenberg_zh.json"

# (输入, 期望命中的编号) —— 编号写死，是为了防止"能搜到但搜到了错的那本"
CASES = [
    ("红楼梦", 24264), ("紅樓夢", 24264),
    ("山海经", 25288), ("山海經", 25288),
    ("三字经", 12479), ("三字經", 12479),
    ("水浒传", 23863), ("水滸傳", 23863),
    ("西游记", 23962), ("西遊記", 23962),
    ("聊斋志异", 51828), ("聊齋志異", 51828),
    ("金瓶梅", 52200),
    ("西厢记", 23906), ("西廂記", 23906),
    ("史记", 24226), ("史記", 24226),
    ("孟子", 24178),
    ("论语", 23839), ("論語", 23839),        # 不能是英文译本 4094
    ("道德经", 7337), ("道德經", 7337),      # 不能是英译本 49965
    ("唐诗三百首", 52323),
    ("二刻拍案惊奇", 24162), ("二刻拍案驚奇", 24162),
    ("闲情偶寄", 25380), ("閒情偶寄", 25380),
    ("三国演义", 23950), ("三國演義", 23950),
    ("封神演义", 23910),
    ("隋唐演义", 23835),
]


def slice_fn(text: str, name: str) -> str:
    """按行号切出一个顶层 def。缩进到顶层的行（非空、非缩进、非 #）算结尾。

    早先图省事用正则 `def X.*?(?=\ndef )`，结果 _norm 在文件后半段，
    中间隔着一整个豆瓣模块，正则把那一大坨全吞进去，执行时报
    name 'GroupMessageEvent' is not defined。按行切干净利落。
    """
    lines = text.splitlines()
    start = None
    for i, ln in enumerate(lines):
        if re.match(rf'^(?:async )?def {name}\b', ln):
            start = i
            break
    if start is None:
        raise SystemExit(f"文件里没有 def {name}")
    for j in range(start + 1, len(lines)):
        ln = lines[j]
        if ln and not ln[0].isspace() and not ln.startswith("#"):
            return "\n".join(lines[start:j])
    return "\n".join(lines[start:])


def slice_assign(text: str, name: str) -> str:
    """切一个顶层赋值，支持括号跨多行。"""
    lines = text.splitlines()
    start = None
    for i, ln in enumerate(lines):
        if ln.startswith(f"{name} ="):
            start = i
            break
    if start is None:
        raise SystemExit(f"文件里没有 {name} =")
    out, depth = [], 0
    for ln in lines[start:]:
        out.append(ln)
        depth += ln.count("(") + ln.count("[") + ln.count("{")
        depth -= ln.count(")") + ln.count("]") + ln.count("}")
        if depth <= 0:
            break
    return "\n".join(out)


def load():
    text = SRC.read_text(encoding="utf-8")
    ns = {"CATALOG": json.loads(CAT.read_text(encoding="utf-8")), "re": re}
    for src in (slice_assign(text, "_HAS_CJK"),
                slice_assign(text, "_T2S_FROM"),
                slice_assign(text, "_T2S_TO"),
                slice_assign(text, "_T2S"),
                slice_fn(text, "_t2s"),
                slice_fn(text, "_norm"),
                slice_fn(text, "match_old")):
        exec(src, ns)
    return ns


def main():
    ns = load()
    match = ns["match_old"]
    bad = []
    for kw, want in CASES:
        r = match(kw)
        if not r:
            bad.append((kw, "未命中", want))
            print(f"✗ {kw:<10} 未命中  期望 {want}")
            continue
        if r["id"] != want:
            bad.append((kw, r["id"], want))
            print(f"✗ {kw:<10} 命中 {r['id']}（《{r['title']}》）期望 {want}")
            continue
        print(f"✓ {kw:<10} {r['id']:<6} 《{r['title']}》")

    total = len(CASES)
    print(f"\n{total - len(bad)}/{total} 通过")
    if bad:
        print("失败项：")
        for b in bad:
            print("  ", b)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
