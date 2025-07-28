# WebStreamer/bot/plugins/stream.py
import logging
import os
from pyrogram import filters, errors
from WebStreamer.vars import Var
from urllib.parse import quote_plus
from WebStreamer.bot import StreamBot, logger
from WebStreamer.utils import get_hash, get_name
from WebStreamer.utils.file_properties import get_media_from_message, parse_file_unique_id
from WebStreamer.bot.database import (
    add_or_update_user, update_stats, insert_link, is_user_banned,
    is_user_authorized, get_user_traffic_details
)
from WebStreamer.bot.i18n import get_i18n_texts
from WebStreamer.ratelimiter import RateLimiter
from pyrogram.enums.parse_mode import ParseMode
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

limiter = RateLimiter()

@StreamBot.on_message(
    filters.private
    & (
        filters.document | filters.video | filters.audio | filters.animation |
        filters.voice | filters.video_note | filters.photo | filters.sticker
    ),
    group=4,
)
async def media_receive_handler(bot, m: Message):
    lang_texts = await get_i18n_texts(m.from_user.id)

    if not await is_user_authorized(m.from_user.id):
        await m.reply_text(lang_texts.get("NOT_AUTHORIZED"), quote=True)
        return

    if await is_user_banned(m.from_user.id):
        await m.reply_text(lang_texts.get("BANNED_USER_ERROR"), quote=True)
        return

    traffic_details = await get_user_traffic_details(m.from_user.id)
    used_traffic_mb = traffic_details.get('total_size', 0.0)
    traffic_limit_gb = traffic_details.get('traffic_limit_gb')

    if traffic_limit_gb is not None:
        traffic_limit_mb = traffic_limit_gb * 1024
        if used_traffic_mb >= traffic_limit_mb:
            await m.reply_text(
                lang_texts.get("TRAFFIC_LIMIT_EXCEEDED").format(traffic_limit_gb=traffic_limit_gb),
                quote=True
            )
            return

    if Var.RATE_LIMIT and limiter.is_limited(m.from_user.id):
        await m.reply_text(
            lang_texts.get("RATE_LIMIT_ERROR").format(time_window=Var.TIME_WINDOW),
            quote=True
        )
        return
    
    original_filename = get_name(m)
    
    if not m.forward_date and m.caption:
        _ , file_extension = os.path.splitext(original_filename)
        custom_base_name = m.caption.replace("\r", " ").replace("\n", " ").strip()
        final_filename = custom_base_name + file_extension
    else:
        final_filename = original_filename

    file_size_in_mb = 0
    media = get_media_from_message(m)
    if media and hasattr(media, 'file_size') and media.file_size > 0:
        file_size_in_mb = media.file_size / (1024 * 1024)
        
    log_msg = await m.copy(chat_id=Var.BIN_CHANNEL)
    
    await add_or_update_user(
        user_id=m.from_user.id,
        first_name=m.from_user.first_name,
        last_name=m.from_user.last_name or '',
        username=m.from_user.username or ''
    )
    await update_stats(m.from_user.id, file_size_in_mb)
    
    file_unique_id = await parse_file_unique_id(m)
    await insert_link(
        user_id=m.from_user.id, link_id=log_msg.id,
        file_name=final_filename, file_size_mb=file_size_in_mb,
        file_unique_id=file_unique_id
    )

    file_hash = get_hash(file_unique_id, Var.HASH_LENGTH)
    stream_link = f"{Var.URL}{log_msg.id}/{quote_plus(final_filename)}?hash={file_hash}"
    
    reply_text = lang_texts.get("LINK_GENERATED").format(
        final_filename=final_filename,
        file_size_in_mb=file_size_in_mb
    )

    reply_markup = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(lang_texts.get("OPEN_LINK_BUTTON"), url=stream_link)],
            [InlineKeyboardButton(lang_texts.get("COPY_LINK_BUTTON"), callback_data=f"copy_{log_msg.id}")]
        ]
    )
    
    await m.reply_text(
        text=reply_text, quote=True,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup, disable_web_page_preview=True
    )

@StreamBot.on_callback_query(filters.regex(r"^copy_"))
async def copy_link_handler(bot, query: CallbackQuery):
    lang_texts = await get_i18n_texts(query.from_user.id)
    message_id = int(query.data.split("_")[1])
    
    try:
        file_info = await bot.get_messages(Var.BIN_CHANNEL, message_id)
        file_name = get_name(file_info)
        file_unique_id = await parse_file_unique_id(file_info)
        file_hash = get_hash(file_unique_id, Var.HASH_LENGTH)
        
        stream_link = f"{Var.URL}{message_id}/{quote_plus(file_name)}?hash={file_hash}"
        
        await query.answer(text=lang_texts.get("LINK_COPIED_SUCCESS"), show_alert=True)
        await bot.send_message(
            chat_id=query.from_user.id,
            text=lang_texts.get("LINK_COPIED_MESSAGE").format(stream_link=stream_link),
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Error in copy handler: {e}")
        await query.answer(text=lang_texts.get("COPY_ERROR"), show_alert=True)