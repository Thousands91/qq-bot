"""重新生成 book_find.py 里的简繁对照表

为什么要嵌表而不是 import opencc：opencc 装完 20MB 左右，机器人跑在手机上，
为了一百多个字的映射多背这么多没必要。目录变动时重跑这个脚本即可。

用法：
    pip install opencc-python-reimplemented
    python3 scripts/gen_t2s.py
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "bot" / "data" / "gutenberg_zh.json"
PLUGIN = ROOT / "bot" / "plugins" / "book_find.py"


def main():
    try:
        import opencc
    except ImportError:
        print("缺 opencc：pip install opencc-python-reimplemented")
        return 1
    cc = opencc.OpenCC("t2s")

    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    chars = set()
    for k, v in cat.items():
        for t in [k, v.get("s", "")] + list(v.get("alias") or []):
            chars.update(c for c in t if "\u4e00" <= c <= "\u9fff")

    pairs = {}
    for c in sorted(chars):
        s = cc.convert(c)
        if s != c and len(s) == 1:
            pairs[c] = s

    src = "".join(pairs)
    dst = "".join(pairs.values())
    if len(src) != len(dst):
        print("❌ 长度不一致，太不安全了，停下")
        return 1

    def wrap(s, n=40):
        return [s[i:i + n] for i in range(0, len(s), n)]

    block = (
        "# 简繁对照：运行时不装 opencc（20MB 的包，手机不必要），\n"
        f"# 用这张表覆盖目录里出现过的繁体字，{len(src)} 个字，够用。\n"
        "# 重新生成：python3 scripts/gen_t2s.py\n"
        "_T2S_FROM = (\n" + "".join(f'    "{l}"\n' for l in wrap(src)) + ")\n"
        "_T2S_TO = (\n" + "".join(f'    "{l}"\n' for l in wrap(dst)) + ")\n"
        "_T2S = str.maketrans(_T2S_FROM, _T2S_TO)\n"
        "\n"
        "\n"
        "def _t2s(t: str) -> str:\n"
        '    """繁体转简体，只为让书名比对能通。表里没有的字原样保留。"""\n'
        '    return (t or "").translate(_T2S)\n'
    )

    text = PLUGIN.read_text(encoding="utf-8")
    # 替换已有的表（从注释头到 _t2s 函数结束）；没有就插在 _HAS_CJK 后面
    pat = re.compile(
        r"# 简繁对照：.*?\ndef _t2s\(t: str\) -> str:\n.*?return \(t or \"\"\)\.translate\(_T2S\)\n",
        re.S,
    )
    if pat.search(text):
        text = pat.sub(block, text)
    else:
        anchor = ('# 判断标题里有没有汉字。\n'
                  '_HAS_CJK = re.compile(r"[\\u4e00-\\u9fff]")\n')
        if anchor not in text:
            print("❌ 找不到插入点，手动看一眼 book_find.py")
            return 1
        text = text.replace(anchor, anchor + "\n" + block)

    PLUGIN.write_text(text, encoding="utf-8")
    print(f"✅ 表已更新：{len(src)} 个字 → {PLUGIN}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
