# WebStreamer/bot/plugins/mylinks.py
from pyrogram import filters, errors
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from WebStreamer.bot import StreamBot
from WebStreamer.bot.database import get_user_links, count_user_links, delete_link
from WebStreamer.bot.i18n import get_i18n_texts
import math

LINKS_PER_PAGE = 5

async def get_links_keyboard(user_id, page, total_links):
    lang_texts = await get_i18n_texts(user_id)
    links = await get_user_links(user_id, offset=page * LINKS_PER_PAGE, limit=LINKS_PER_PAGE)
    
    keyboard = []
    for link in links:
        button_text = lang_texts.get("DELETE_BUTTON_TEXT").format(
            file_name=link['file_name'],
            file_size_mb=link['file_size_mb']
        )
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"delete_{link['id']}_{page}")])

    if total_links > LINKS_PER_PAGE:
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton(f"◀️ {lang_texts.get('PREVIOUS_BUTTON')}", callback_data=f"page_{page-1}"))
        if (page + 1) * LINKS_PER_PAGE < total_links:
            nav_buttons.append(InlineKeyboardButton(f"{lang_texts.get('NEXT_BUTTON')} ▶️", callback_data=f"page_{page+1}"))
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
    await m.reply_text(
        lang_texts.get("MYLINKS_HEADER"),
        reply_markup=keyboard,
        quote=True
    )

@StreamBot.on_callback_query(filters.regex(r"^(page_|delete_)"))
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
            await query.message.edit_reply_markup(reply_markup=keyboard)
            await query.answer()
        except errors.MessageNotModified:
            await query.answer(lang_texts.get("SAME_PAGE_NOTICE"))

    elif action == "delete":
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
        await query.message.edit_reply_markup(reply_markup=keyboard)