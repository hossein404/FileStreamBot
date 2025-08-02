# WebStreamer/bot/plugins/mylinks.py
from pyrogram import filters, errors
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from WebStreamer.bot import StreamBot
from WebStreamer.bot.database import get_user_links, count_user_links, delete_link, get_link_by_id
from WebStreamer.bot.i18n import get_i18n_texts
from WebStreamer.utils.file_properties import get_hash
from WebStreamer.vars import Var
from urllib.parse import quote_plus
import math

LINKS_PER_PAGE = 5

async def get_links_keyboard(user_id, page, total_links):
    lang_texts = await get_i18n_texts(user_id)
    links = await get_user_links(user_id, offset=page * LINKS_PER_PAGE, limit=LINKS_PER_PAGE)
    
    keyboard = []
    for link in links:
        views = link.get('views', 0)
        button_text = f"👁 {views} | {link['file_name']} ({link['file_size_mb']:.2f} MB)"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"mylink_{link['id']}_{page}")])

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(f"◀️ {lang_texts.get('PREVIOUS_BUTTON')}", callback_data=f"page_{page-1}"))
    if (page + 1) * LINKS_PER_PAGE < total_links:
        nav_buttons.append(InlineKeyboardButton(f"{lang_texts.get('NEXT_BUTTON')} ▶️", callback_data=f"page_{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
        
    return InlineKeyboardMarkup(keyboard) if keyboard else None

@StreamBot.on_message(filters.command("mylinks") & filters.private)
async def mylinks_handler(bot, m: Message):
    user_id = m.from_user.id
    lang_texts = await get_i18n_texts(user_id)
    total_links = await count_user_links(user_id)

    if total_links == 0:
        await m.reply_text(lang_texts.get("NO_LINKS_YET"), quote=True)
        return

    keyboard = await get_links_keyboard(user_id, 0, total_links)
    await m.reply_text(lang_texts.get("MYLINKS_HEADER"), reply_markup=keyboard, quote=True)

@StreamBot.on_callback_query(filters.regex(r"^(page|mylink|getlink|confirmdelete)_"))
async def links_callback_handler(bot, query: CallbackQuery):
    user_id = query.from_user.id
    lang_texts = await get_i18n_texts(user_id)
    data = query.data.split("_")
    action = data[0]

    if action == "page":
        page = int(data[1])
        total_links = await count_user_links(user_id)
        keyboard = await get_links_keyboard(user_id, page, total_links)
        try:
            await query.message.edit_text(lang_texts.get("MYLINKS_HEADER"), reply_markup=keyboard)
        except errors.MessageNotModified:
            await query.answer(lang_texts.get("SAME_PAGE_NOTICE"))

    elif action == "mylink":
        link_id = int(data[1])
        page = int(data[2])
        link_info = await get_link_by_id(link_id)
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(lang_texts.get("mylinks_get_link"), callback_data=f"getlink_{link_id}")],
            [InlineKeyboardButton(lang_texts.get("mylinks_delete_link"), callback_data=f"confirmdelete_{link_id}_{page}")],
            [InlineKeyboardButton(lang_texts.get("mylinks_back"), callback_data=f"page_{page}")]
        ])
        await query.message.edit_text(
            lang_texts.get("mylinks_choose_action").format(file_name=link_info['file_name']),
            reply_markup=keyboard
        )

    elif action == "getlink":
        link_id = int(data[1])
        link_info = await get_link_by_id(link_id)
        if not link_info:
            await query.answer(lang_texts.get("mylinks_link_not_found"), show_alert=True)
            return

        file_hash = get_hash(link_info['file_unique_id'], Var.HASH_LENGTH)
        stream_link = f"{Var.URL}{link_info['id']}/{quote_plus(link_info['file_name'])}?hash={file_hash}"
        
        await bot.send_message(
            chat_id=user_id,
            text=lang_texts.get("LINK_COPIED_MESSAGE").format(stream_link=stream_link)
        )
        await query.answer(lang_texts.get("mylinks_link_sent"), show_alert=True)
        
    elif action == "confirmdelete":
        link_id = int(data[1])
        page = int(data[2])
        await delete_link(link_id, user_id)
        await query.answer(lang_texts.get("LINK_DELETED_SUCCESS"), show_alert=True)
        total_links = await count_user_links(user_id)
        if total_links == 0:
            await query.message.edit_text(lang_texts.get("ALL_LINKS_DELETED"))
            return
        if page > 0 and page >= math.ceil(total_links / LINKS_PER_PAGE):
            page -= 1
        keyboard = await get_links_keyboard(user_id, page, total_links)
        await query.message.edit_text(lang_texts.get("MYLINKS_HEADER"), reply_markup=keyboard)
        
    await query.answer()