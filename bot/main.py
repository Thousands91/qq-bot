"""
NoneBot 启动入口
"""

from pathlib import Path
import sys

from nonebot import init, load_plugins, get_driver

from config import config

# 让 persona 能被插件 import
sys.path.insert(0, str(Path(__file__).parent))

# 初始化
init(config)

# 加载所有插件
plugins_path = Path(__file__).parent / "plugins"
load_plugins(str(plugins_path))


@get_driver().on_startup
async def _startup():
    from loguru import logger
    logger.info("=" * 50)
    logger.info("QQ 群机器人启动成功 ✅")
    logger.info("请确认 go-cqhttp 已扫码登录")
    logger.info("=" * 50)


if __name__ == "__main__":
    from nonebot import run
    run()
