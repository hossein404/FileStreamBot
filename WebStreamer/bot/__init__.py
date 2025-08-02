# WebStreamer/bot/__init__.py
import os
from ..vars import Var
import logging
from pyrogram import Client

logger = logging.getLogger("bot")

sessions_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sessions")
if Var.USE_SESSION_FILE:
    logger.info("Using session files")
    logger.info(f"Session folder path: {sessions_dir}")
    if not os.path.isdir(sessions_dir):
        os.makedirs(sessions_dir)

StreamBot = Client(
    name="WebStreamer",
    api_id=Var.API_ID,
    api_hash=Var.API_HASH,
    plugins=dict(root="WebStreamer.bot.plugins"),
    bot_token=Var.BOT_TOKEN,
    sleep_threshold=Var.SLEEP_THRESHOLD,
    workers=Var.WORKERS,
    in_memory=not Var.USE_SESSION_FILE,
)

multi_clients = {}
work_loads = {}