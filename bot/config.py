from pathlib import Path

from dotenv import load_dotenv
from nonebot.config import Env, Config

# 加载 .env
load_dotenv(Path(__file__).parent / ".env")

env = Env()

# 默认配置（可被 .env 同名项覆盖）
defaults = {
    "superusers": set(),
    "nickname": {"Bot", "机器人", "bot", "BOT"},
    # 空字符串让命令不带前缀也能用；.env 里的 COMMAND_START 是同一件事的权威来源
    "command_start": {"", "/", "!", "！"},
    "apscheduler_autostart": True,
    "apscheduler_config": {"apscheduler.timezone": "Asia/Shanghai"},
}

# 先合并再传：defaults 和 env 里同名键重复传会报 TypeError
_merged = {**defaults, **env.dict()}
config = Config(**_merged)
