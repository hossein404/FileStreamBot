# WebStreamer/bot/plugins/stream.py
import logging
import os
import re
from asyncio import sleep
from pyrogram import filters, errors
from WebStreamer.vars import Var
from urllib.parse import quote_plus
from WebStreamer.bot import StreamBot
from WebStreamer.utils import get_hash, get_name
from WebStreamer.utils.file_properties import get_media_from_message, parse_file_unique_id
from WebStreamer.bot.database import (
    add_or_update_user, update_stats, insert_link, is_user_banned,
    is_user_authorized, get_user_traffic_details, get_link_by_id
)
from WebStreamer.bot.i18n import get_i18n_texts
from WebStreamer.bot.config import config
from WebStreamer.ratelimiter import RateLimiter
from pyrogram.enums.parse_mode import ParseMode
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# A logger for this specific file
logger = logging.getLogger(__name__)

limiter = RateLimiter()
media_group_cache = {}
album_links_cache = {}
BUTTONS_PER_PAGE = 4

def create_album_keyboard(links: list, media_group_id: str, lang_texts: dict, page: int = 0):
    keyboard = []
    start_index = page * BUTTONS_PER_PAGE
    end_index = start_index + BUTTONS_PER_PAGE
    
    for file_name, link_id in links[start_index:end_index]:
        keyboard.append([InlineKeyboardButton(file_name, callback_data=f"copyalbum_{link_id}")])

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(f"◀️ {lang_texts.get('PREVIOUS_BUTTON')}", callback_data=f"album_{media_group_id}_{page-1}"))
    if end_index < len(links):
        nav_buttons.append(InlineKeyboardButton(f"{lang_texts.get('NEXT_BUTTON')} ▶️", callback_data=f"album_{media_group_id}_{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
        
    return InlineKeyboardMarkup(keyboard)

async def generate_single_link(m: Message):
    lang_texts = await get_i18n_texts(m.from_user.id)
    if not await is_user_authorized(m.from_user.id):
        await m.reply_text(lang_texts.get("NOT_AUTHORIZED"), quote=True); return None, None
    original_filename = get_name(m)
    custom_base_name = m.caption.replace("\r", " ").replace("\n", " ").strip() if not m.forward_date and m.caption else None
    final_filename = (secure_filename(custom_base_name) + os.path.splitext(original_filename)[1]) if custom_base_name else original_filename
    media = get_media_from_message(m)
    file_size_in_mb = media.file_size / (1024 * 1024) if media and media.file_size else 0
    log_msg = await m.copy(chat_id=Var.BIN_CHANNEL)
    file_unique_id = await parse_file_unique_id(m)
    await add_or_update_user(m.from_user.id, m.from_user.first_name, m.from_user.last_name or '', m.from_user.username or '')
    await update_stats(m.from_user.id, file_size_in_mb)
    await insert_link(m.from_user.id, log_msg.id, final_filename, file_size_in_mb, file_unique_id)

    # --- این خط جدید برای ثبت لاگ است ---
    logger.info(f"Link generated for user {m.from_user.id} (@{m.from_user.username}). File: '{final_filename}', Link ID: {log_msg.id}")
    # ------------------------------------

    return final_filename, log_msg.id

@StreamBot.on_message(
    filters.private & (filters.document | filters.video | filters.audio | filters.animation | filters.voice | filters.video_note | filters.photo | filters.sticker),
    group=4,
)
async def media_receive_handler(bot: StreamBot, m: Message):
    lang_texts = await get_i18n_texts(m.from_user.id)
    if m.media_group_id:
        if m.media_group_id not in media_group_cache:
            media_group_cache[m.media_group_id] = []
        media_group_cache[m.media_group_id].append(m)
        await sleep(1.5)
        try:
            if len(await bot.get_media_group(m.chat.id, m.id)) != len(media_group_cache.get(m.media_group_id, [])):
                return
        except Exception: return
        messages = media_group_cache.pop(m.media_group_id)
        messages.sort(key=lambda x: x.id)
        status_message = await m.reply_text(lang_texts.get("album_processing"), quote=True)
        links = []
        for message in messages:
            final_filename, log_msg_id = await generate_single_link(message)
            if log_msg_id:
                links.append((final_filename, log_msg_id))
        if links:
            media_group_id = str(m.media_group_id)
            album_links_cache[media_group_id] = links
            keyboard = create_album_keyboard(links, media_group_id, lang_texts, page=0)
            await status_message.edit_text(lang_texts.get("album_success"), reply_markup=keyboard)
        else:
            await status_message.edit_text(lang_texts.get("album_error"))
        return

    final_filename, log_msg_id = await generate_single_link(m)
    if log_msg_id:
        link_info = await get_link_by_id(log_msg_id)
        file_hash = get_hash(link_info['file_unique_id'], Var.HASH_LENGTH)
        stream_link = f"{Var.URL}{link_info['id']}/{quote_plus(link_info['file_name'])}?hash={file_hash}"
        media = get_media_from_message(m)
        file_size_in_mb = (media.file_size / (1024*1024)) if media and media.file_size else 0
        reply_text = lang_texts.get("LINK_GENERATED").format(final_filename=final_filename, file_size_in_mb=file_size_in_mb)
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(lang_texts.get("OPEN_LINK_BUTTON"), url=stream_link)],
            [InlineKeyboardButton(lang_texts.get("COPY_LINK_BUTTON"), callback_data=f"copy_{log_msg_id}")]
        ])
        await m.reply_text(text=reply_text, quote=True, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup, disable_web_page_preview=True)

@StreamBot.on_callback_query(filters.regex(r"^(album_|copyalbum_|copy_)"))
async def unified_callback_handler(bot, query: CallbackQuery):
    lang_texts = await get_i18n_texts(query.from_user.id)
    data_parts = query.data.split("_")
    action = data_parts[0]

    if action == "album":
        media_group_id, page_str = data_parts[1], data_parts[2]
        page = int(page_str)
        links = album_links_cache.get(media_group_id)
        if not links:
            await query.answer("Error: Album data has expired.", show_alert=True); return
        keyboard = create_album_keyboard(links, media_group_id, lang_texts, page)
        try: await query.message.edit_reply_markup(keyboard)
        except errors.MessageNotModified: await query.answer()

    elif action in ["copyalbum", "copy"]:
        link_id = int(data_parts[1])
        link_info = await get_link_by_id(link_id)
        if not link_info:
            await query.answer(lang_texts.get("mylinks_link_not_found"), show_alert=True); return
        file_hash = get_hash(link_info['file_unique_id'], Var.HASH_LENGTH)
        stream_link = f"{Var.URL}{link_info['id']}/{quote_plus(link_info['file_name'])}?hash={file_hash}"
        await bot.send_message(
            chat_id=query.from_user.id,
            text=lang_texts.get("LINK_COPIED_MESSAGE").format(stream_link=stream_link)
        )
        await query.answer(lang_texts.get("LINK_COPIED_SUCCESS"), show_alert=True)