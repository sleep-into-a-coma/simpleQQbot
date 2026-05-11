from nonebot import get_driver
from lib.config import load_config
from lib.db import init_db

driver = get_driver()
app_config = load_config()

@driver.on_startup
async def on_startup():
    await init_db()


from .handlers import *  # noqa
from .router import *  # noqa
