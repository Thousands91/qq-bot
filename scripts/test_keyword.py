"""校验关键词触发：同义词整句匹配，不中即沉默

触发规则是"整句等于关键词（允许后跟语气词/称呼）"，没有包含匹配。
这个脚本一半用例是"不该触发"——误触是历史上真实发生过两次的毛病
（单字"书"、"今天早上好冷啊"撞"早上好"），每次改都跑一遍这里。

用法：
    python3 scripts/test_keyword.py
"""
import re
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "bot" / "plugins" / "keyword_reply.py"

# (消息, 期望命中的关键词或 None)
CASES = [
    # —— 同义词变体，都该触发 ——
    # 期望值写的是"实际命中的那个同义词"，不是组名——
    # 命中哪个变体不重要，重要的是落到同一个回复池。
    ("早上好", "早上好"),
    ("早安", "早安"),
    ("早", "早"),
    ("早啊", "早啊"),
    ("早上好啊", "早上好啊"),
    ("早上好！", "早上好"),           # 标点不算
    ("早上好呀朋友们", "早上好呀"),    # 表里有"早上好呀"，长词优先
    ("早安，各位！", "早安"),
    ("晚上好", "晚上好"),
    ("晚安啦", "晚安啦"),
    ("睡了", "睡了"),
    ("你好", "你好"),
    ("您好", "您好"),
    ("hi", "hi"),
    ("Hello", "hello"),              # 大小写
    ("哈喽", "哈喽"),
    ("你好呀老板", "你好"),
    ("谢谢", "谢谢"),
    ("多谢", "多谢"),
    ("感谢老板", "感谢"),
    ("谢谢你", "谢谢"),

    # —— 其它关键词，整句触发 ——
    ("苏丹", "苏丹"),
    ("苏丹卡", "苏丹卡"),             # 长词优先
    ("百科全书", "百科全书"),
    ("阿萨尔", "阿萨尔"),
    ("菜单", "菜单"),
    ("找书", "找书"),

    # —— 不该触发的（这是重点） ——
    ("今天早上好冷啊", None),         # 历史 bug：包含匹配时代会触发
    ("早上好困", None),
    ("这早上好无聊", None),
    ("咱们晚上好吵", None),
    ("你好好休息", None),
    ("晚安之前", None),
    ("他说了声谢谢就走了", None),
    ("今天早上吃什么，好吃吗？", None),
    ("这本书不错", None),
    ("书架上落灰了", None),
    ("看说明书", None),
    ("苏丹红是什么", None),           # 苏丹红是色素；包含匹配时代会误触
    ("各位早上好", None),             # 前置称呼不认——这是已知代价
    ("群主今天没来", None),           # 群主已从关键词表移除
    ("群主", None),                   # 同上：单独喊群主也不再应答
    ("我在看阿萨尔那本书", None),
    ("帮我找书", None),              # 要触发请用 /找书 命令
    ("今晚吃什么呢", None),
    ("随便说点什么", None),
    ("/找书 三体", None),            # 命令前缀不抢
    ("!点歌 晴天", None),
]


def load():
    text = SRC.read_text(encoding="utf-8")
    ns = {"random": __import__("random")}
    exec("import re", ns)
    exec(re.search(r"REPLIES = \{.*?\n\}\n", text, re.S).group(0), ns)
    exec(re.search(r"TAIL_WORDS = \[.*?\]\n", text, re.S).group(0), ns)
    exec(re.search(r"def _keys.*?return \[item\] if.*?\n", text, re.S).group(0), ns)
    exec(re.search(r"def _match.*?(?=\n@kw_reply|\n\ndef )", text, re.S).group(0), ns)
    return ns


def main():
    ns = load()
    match = ns["_match"]
    bad = []
    for msg, want in CASES:
        m = match(msg)
        got = m[0] if m else None
        ok = got == want
        if not ok:
            bad.append((msg, got, want))
        print(f"{'✓' if ok else '✗'} {msg:<18} → {got or '（沉默）':<10} 期望 {want or '（沉默）'}")

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
