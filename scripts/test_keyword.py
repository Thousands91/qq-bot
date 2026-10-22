"""校验关键词触发：哪些该触发、哪些不该触发

关键词回复最容易出的问题是"误触"——群里正常聊天，机器人突然插一句。
所以这个脚本一半用例是"不该触发"。

用法：
    python3 scripts/test_keyword.py
"""
import re
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "bot" / "plugins" / "keyword_reply.py"

# (消息, 期望命中的关键词或 None)
CASES = [
    # —— 该触发的 ——
    ("你好", "你好"),
    # 同长度时"你好"排在前面，这是预期行为（回"您好"也没什么不对）
    ("群主你好啊", "你好"),
    ("今天早上好冷", "早上好"),
    ("晚安啦", "晚安"),
    ("我谢谢你了", "谢谢"),
    ("苏丹卡怎么折", "苏丹卡"),     # 长词优先，不该回"苏丹"
    ("杀戮卡要不要留", "杀戮卡"),
    ("他在编百科全书", "百科全书"),
    ("阿萨尔", "阿萨尔"),
    ("菜单", "菜单"),
    # "来首歌"是点歌命令的别名，不该被关键词插件抢。
    # 这里模拟的是"没带 / 前缀时是否会被关键词吃下"——答案是会，
    # 但 on_command 的优先级更高，实际不会冲突。
    ("来首歌", None),

    # —— 不该触发的 ——
    ("这本书不错", None),           # 原来会触发"书"，现在不会
    ("书架上落灰了", None),
    ("看说明书", None),
    ("今晚月色很好", None),
    ("/找书 三体", None),           # 带命令前缀不抢答
    ("!点歌 晴天", None),
    ("今天下雨了", None),
    ("随便说点什么", None),
]


def load():
    text = SRC.read_text(encoding="utf-8")
    src = re.search(r"REPLIES = \{.*?\n\}\n", text, re.S).group(0)
    ns = {"random": __import__("random")}
    exec(src, ns)
    exec(re.search(r"def _keys.*?return .*?\n", text, re.S).group(0), ns)
    return ns


def simulate(text, replies, keys):
    """照抄 handler 的判断逻辑，不启动 nonebot。"""
    t = text.strip().lower()
    if not t or t[0] in ("/", "!", "！"):
        return None
    pairs = []
    for item, rs in replies.items():
        for kw in keys(item):
            pairs.append((kw, rs))
    pairs.sort(key=lambda p: len(p[0]), reverse=True)
    for kw, rs in pairs:
        if t == kw.lower():
            return kw
    for kw, rs in pairs:
        if kw.lower() in t:
            return kw
    return None


def main():
    ns = load()
    replies, keys = ns["REPLIES"], ns["_keys"]
    bad = []
    for msg, want in CASES:
        got = simulate(msg, replies, keys)
        ok = (got == want)
        if not ok:
            bad.append((msg, got, want))
        print(f"{'✓' if ok else '✗'} {msg:<16} 命中={got!r:<12} 期望={want!r}")

    print(f"\n{len(CASES)-len(bad)}/{len(CASES)} 通过")
    if bad:
        for b in bad:
            print("  失败:", b)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
