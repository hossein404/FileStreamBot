# WebStreamer/__main__.py
import sys
import asyncio
import logging
import os
from .vars import Var
from aiohttp import web
from pyrogram import idle
from WebStreamer import utils
from WebStreamer import StreamBot
from WebStreamer.server import web_server
from WebStreamer.bot.clients import initialize_clients
from WebStreamer.bot.database import init_db
from WebStreamer.bot.config import config

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE_PATH = os.path.join(os.path.dirname(ROOT_DIR), "streambot.log")

log = logging.getLogger()
log.setLevel(logging.INFO)

formatter = logging.Formatter(
    "[%(asctime)s][%(name)s][%(levelname)s] ==> %(message)s",
    datefmt="%d/%m/%Y %H:%M:%S"
)

stream_handler = logging.StreamHandler(stream=sys.stdout)
stream_handler.setFormatter(formatter)
log.addHandler(stream_handler)

try:
    file_handler = logging.FileHandler(LOG_FILE_PATH, mode="a", encoding="utf-8")
    file_handler.setFormatter(formatter)
    log.addHandler(file_handler)
except PermissionError:
    log.warning(f"Permission denied to write to log file: {LOG_FILE_PATH}")

logging.getLogger("aiohttp").setLevel(logging.ERROR)
logging.getLogger("pyrogram").setLevel(logging.INFO)
logging.getLogger("aiohttp.web").setLevel(logging.ERROR)

loop = asyncio.get_event_loop()

async def start_services():
    log.info("-------------------- STARTING BOT --------------------")
    log.info(f"Log file is at: {LOG_FILE_PATH}")
    log.info("Initializing Database")
    await init_db()
    
    log.info("Loading configuration from DB")
    await config.load_from_db()
    
    log.info("Initializing Telegram Bot")
    await StreamBot.start()
    bot_info = await StreamBot.get_me()
    StreamBot.username = bot_info.username
    log.info(f"Bot @{StreamBot.username} started!")
    await initialize_clients()
    
    app = web_server(bot=StreamBot)
    runner = web.AppRunner(app)
    await runner.setup()
    
    if Var.KEEP_ALIVE:
        asyncio.create_task(utils.ping_server())
        
    site = web.TCPSite(runner, Var.BIND_ADDRESS, Var.PORT)
    await site.start()
    log.info(f"Web server started at http://{Var.BIND_ADDRESS}:{Var.PORT}")
    await idle()
    await runner.cleanup()

if __name__ == "__main__":
    try:
        loop.run_until_complete(start_services())
    except KeyboardInterrupt:
        log.info("Received stop signal. Shutting down.")
    except Exception as err:
        log.error(err, exc_info=True)
    finally:
        loop.stop()
        log.info("-------------------- BOT STOPPED ---------------------")