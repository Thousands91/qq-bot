"""
NoneBot 启动入口
"""

import sys
from pathlib import Path

from nonebot import get_driver, init, load_plugins

from config import config  # noqa: F401  导入即完成配置注册

# 让 persona 能被插件 import
sys.path.insert(0, str(Path(__file__).parent))

# 初始化（NoneBot 2.x 的 init() 不接受参数）
init()

# 必须显式注册适配器，否则机器人收不到任何 QQ 消息
from nonebot.adapters.onebot.v11 import Adapter  # noqa: E402

get_driver().register_adapter(Adapter)

# 加载所有插件
plugins_path = Path(__file__).parent / "plugins"
load_plugins(str(plugins_path))


@get_driver().on_startup
async def _startup():
    from loguru import logger

    logger.info("=" * 50)
    logger.info("QQ 群机器人启动成功 ✅")
    logger.info("OneBot v11 反向 WS：/onebot/v11/ws")
    logger.info("请确认 NapCat / go-cqhttp 已登录")
    logger.info("=" * 50)


if __name__ == "__main__":
    from nonebot import run

    run()
