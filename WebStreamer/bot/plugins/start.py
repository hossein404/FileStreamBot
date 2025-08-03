# WebStreamer/bot/plugins/start.py
from pyrogram import filters, Client
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from WebStreamer.vars import Var
from WebStreamer.bot import StreamBot
from WebStreamer.bot.database import add_or_update_user, is_user_authorized, set_user_lang, is_user_banned
from WebStreamer.bot.i18n import get_i18n_texts

@StreamBot.on_message(filters.command(["start", "help"]) & filters.private)
async def start(bot: Client, m: Message):
    lang_texts = await get_i18n_texts(m.from_user.id)
    user_id = m.from_user.id

    # 🛑 بررسی مسدود بودن کاربر
    if await is_user_banned(user_id):
        return await m.reply(lang_texts.get("BANNED_USER_ERROR"), quote=True)

    # 🛑 بررسی مجاز بودن کاربر
    if not await is_user_authorized(user_id):
        return await m.reply(lang_texts.get("NOT_AUTHORIZED"), quote=True)

    await add_or_update_user(
        user_id=user_id,
        first_name=m.from_user.first_name,
        last_name=m.from_user.last_name or '',
        username=m.from_user.username or ''
    )
    
    start_text = lang_texts.get("START_TEXT").format(mention=m.from_user.mention(style='md'))
    if Var.RATE_LIMIT:
        start_text += lang_texts.get("RATE_LIMIT_INFO").format(max_requests=Var.MAX_REQUESTS, time_window=Var.TIME_WINDOW)
    start_text += lang_texts.get("START_FOOTER")

    reply_markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🇮🇷 فارسی", callback_data="set_lang_fa"),
                InlineKeyboardButton("🇬🇧 English", callback_data="set_lang_en")
            ],
            [InlineKeyboardButton(lang_texts.get("DEVELOPER_BUTTON"), url="https://t.me/iamast3r")]
        ]
    )
    
    await m.reply_text(
        text=start_text,
        reply_markup=reply_markup,
        disable_web_page_preview=True,
        quote=True
    )

@StreamBot.on_callback_query(filters.regex("^set_lang_"))
async def language_setter(bot: Client, query: CallbackQuery):
    lang_code = query.data.split("_")[-1]
    await set_user_lang(query.from_user.id, lang_code)
    
    lang_texts = await get_i18n_texts(query.from_user.id)
    await query.answer(lang_texts.get("LANGUAGE_CHANGED"), show_alert=True)
    
    start_text = lang_texts.get("START_TEXT").format(mention=query.from_user.mention(style='md'))
    if Var.RATE_LIMIT:
        start_text += lang_texts.get("RATE_LIMIT_INFO").format(max_requests=Var.MAX_REQUESTS, time_window=Var.TIME_WINDOW)
    start_text += lang_texts.get("START_FOOTER")

    reply_markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🇮🇷 فارسی", callback_data="set_lang_fa"),
                InlineKeyboardButton("🇬🇧 English", callback_data="set_lang_en")
            ],
            [InlineKeyboardButton(lang_texts.get("DEVELOPER_BUTTON"), url="https://t.me/iamast3r")]
        ]
    )

    try:
        await query.message.edit_text(start_text, reply_markup=reply_markup, disable_web_page_preview=True)
    except: # MessageNotModified
        pass