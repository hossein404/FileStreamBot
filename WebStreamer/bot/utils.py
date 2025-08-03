# WebStreamer/bot/utils.py
import logging
from WebStreamer.bot.config import config
from WebStreamer.bot import StreamBot
from pyrogram.errors import UserNotParticipant

logger = logging.getLogger(__name__)

async def check_user_is_member(user_id: int):
    """
    Checks if a user is a member of the force subscription channel using live config.
    Returns a tuple: (is_member: bool, error_message: str | None, channel_link: str | None)
    """
    if not config.force_sub_channel or config.force_sub_channel == 0:
        return True, None, None

    try:
        await StreamBot.get_chat_member(config.force_sub_channel, user_id)
        return True, None, None
    except UserNotParticipant:
        try:
            chat = await StreamBot.get_chat(config.force_sub_channel)
            invite_link = chat.invite_link
            if not invite_link:
                logger.warning(f"Bot is in channel {config.force_sub_channel} but cannot get an invite link.")
                return True, "no_invite_link", None
            return False, "not_member", invite_link
        except Exception as e:
            logger.error(f"Error checking force sub channel: {e}. Bot might not be an admin in {config.force_sub_channel}.")
            return True, "bot_not_admin", None
    except Exception as e:
        logger.error(f"An unexpected error occurred in check_user_is_member: {e}")
        return True, None, None
