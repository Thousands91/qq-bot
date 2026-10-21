"""
AI 智能问答插件
@机器人 + 问题 → 调用大模型回答

支持 OpenAI 兼容协议，可换国内服务：
- 硅基流动 https://siliconflow.cn (推荐，注册送额度)
- DeepSeek https://platform.deepseek.com
- 智谱 BigModel https://bigmodel.cn
- 字节豆包 https://www.volcengine.com/product/doubao
- 月之暗面 https://platform.moonshot.cn
"""
import os
import time
from collections import defaultdict, deque
from typing import Deque, Dict, List

from nonebot import on_message, get_driver
from nonebot.rule import command
from nonebot.permission import SUPERUSER
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message
from nonebot.typing import T_State

ENABLE = os.getenv("ENABLE_AI_CHAT", "true").lower() == "true"
API_KEY = os.getenv("OPENAI_API_KEY", "")
BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.siliconflow.cn/v1")
MODEL = os.getenv("OPENAI_MODEL", "Qwen/Qwen2.5-7B-Instruct")
MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", "800"))
CONTEXT_LEN = int(os.getenv("AI_CONTEXT_LENGTH", "6"))

# 简单的对话上下文（按 (群号, 用户QQ) 缓存最近 N 条）
HISTORY: Dict[tuple, Deque[dict]] = defaultdict(lambda: deque(maxlen=CONTEXT_LEN))

SYSTEM_PROMPT = """你是 QQ 群里的一个中文智能助手，名叫"小派"。
- 用中文回答，简短、幽默、有用。
- 适当使用 emoji 让回复更生动，但不要滥用。
- 如果不清楚就坦诚说不知道。
- 不要回答违法、色情、政治敏感内容。
"""

# 匹配：被 @ 的群消息 / 私聊消息
ai_chat = on_message(priority=99, block=False)


@ai_chat.handle()
async def _(bot: Bot, event: GroupMessageEvent, state: T_State):
    if not ENABLE or not API_KEY:
        return

    # 必须@机器人
    if not event.is_tome():
        return

    text = event.get_plaintext().strip()
    if not text:
        await ai_chat.finish(Message("在呢，有什么想聊的？🤖"))

    # 截流：有些插件有更具体的命令（/天气 /抽签 等），不在 AI 里处理
    if text.startswith(("/", "!", "！")):
        return

    # 构造上下文
    key = (event.group_id, event.user_id)
    msgs: List[dict] = HISTORY[key]
    msgs.append({"role": "user", "content": text})

    try:
        answer = await call_llm(list(msgs))
    except Exception as e:
        await ai_chat.finish(Message(f"AI 调用失败：{type(e).__name__}\n请检查 API Key / 网络"))

    # 缓存回复
    msgs.append({"role": "assistant", "content": answer})
    if len(msgs) > CONTEXT_LEN:
        # 清空历史，避免长期记忆太长
        HISTORY[key].clear()

    # 截断超长回复（QQ 单条限制约 4500 字）
    if len(answer) > 4000:
        answer = answer[:4000] + "\n...(内容过长已截断)"

    await ai_chat.finish(Message(answer))


async def call_llm(messages: List[dict]) -> str:
    """调用 OpenAI 兼容协议"""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)
    full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages

    resp = await client.chat.completions.create(
        model=MODEL,
        messages=full_messages,
        max_tokens=MAX_TOKENS,
        temperature=0.7,
    )
    return (resp.choices[0].message.content or "").strip()


# 清空会话
clear = on_message(command("清空记忆", "重置记忆"), priority=10, block=True)


@clear.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    HISTORY.pop((event.group_id, event.user_id), None)
    await clear.finish("已清空你和我的对话记忆 🧹")
