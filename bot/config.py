from pathlib import Path

from dotenv import load_dotenv
from nonebot.config import Env, Config

# 加载 .env
load_dotenv(Path(__file__).parent / ".env")

env = Env()

# 默认配置
defaults = {
    "superusers": set(),
    "nickname": {"Bot", "机器人", "bot", "BOT"},
    "command_start": {"/", "!", "！"},
    "apscheduler_autostart": True,
    "apscheduler_config": {"apscheduler.timezone": "Asia/Shanghai"},
}

config = Config(**defaults, **env.dict())
