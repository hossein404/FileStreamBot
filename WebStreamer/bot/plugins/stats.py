# WebStreamer/bot/plugins/stats.py
from pyrogram import filters, errors
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from WebStreamer.bot import StreamBot
from WebStreamer.bot.database import get_user_traffic_details, get_stats
from WebStreamer.bot.i18n import get_i18n_texts
from datetime import datetime
import pytz

def get_current_time():
    return datetime.now(pytz.timezone("Asia/Tehran")).strftime("%Y-%m-%d %H:%M:%S")

async def get_stats_text_and_markup(user_id: int):
    lang_texts = await get_i18n_texts(user_id)
    file_count, _ = await get_stats(user_id)
    traffic_details = await get_user_traffic_details(user_id)
    
    used_mb = traffic_details.get('total_size', 0.0)
    used_gb = used_mb / 1024
    limit_gb = traffic_details.get('traffic_limit_gb')

    progress_text = ""
    if limit_gb is not None:
        remaining_gb = limit_gb - used_gb
        limit_str = f"{limit_gb:.2f} GB"
        remaining_str = f"{remaining_gb:.2f} GB"
        percentage = (used_gb / limit_gb) * 100 if limit_gb > 0 else 0
        progress_bar = "[" + "■" * int(percentage / 10) + "□" * (10 - int(percentage / 10)) + "]"
        progress_text = lang_texts.get("USAGE_PROGRESS").format(
            progress_text=f"`{progress_bar} {percentage:.1f}%`"
        )
    else:
        limit_str = lang_texts.get("UNLIMITED")
        remaining_str = lang_texts.get("UNLIMITED")

    stats_message = (
        f"📊 **{lang_texts.get('ACCOUNT_STATS_HEADER')}**\n\n"
        f"🗂 **{lang_texts.get('TOTAL_FILES').format(file_count=file_count)}**\n\n"
        f"**--- {lang_texts.get('TRAFFIC_STATS_HEADER')} ---**\n"
        f"📥 **{lang_texts.get('USED_TRAFFIC').format(used_gb=used_gb)}**\n"
        f"📈 **{lang_texts.get('TOTAL_LIMIT').format(limit_str=limit_str)}**\n"
    )
    
    if limit_gb is not None:
        stats_message += f"📤 **{lang_texts.get('REMAINING_TRAFFIC').format(remaining_str=remaining_str)}**\n\n"
        stats_message += f"{progress_text}\n\n"
    else:
        stats_message += "\n"

    stats_message += f"_{get_current_time()}_"
    
    reply_markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton(f"🔄 {lang_texts.get('REFRESH_BUTTON')}", callback_data="refresh_stats")]]
    )
    
    return stats_message, reply_markup

@StreamBot.on_message(filters.command(["stats", "account"]) & filters.private)
async def stats_handler(bot, m: Message):
    stats_text, markup = await get_stats_text_and_markup(m.from_user.id)
    await m.reply_text(stats_text, quote=True, reply_markup=markup)

@StreamBot.on_callback_query(filters.regex("^refresh_stats"))
async def refresh_stats_handler(bot, query: CallbackQuery):
    lang_texts = await get_i18n_texts(query.from_user.id)
    try:
        stats_text, markup = await get_stats_text_and_markup(query.from_user.id)
        await query.message.edit_text(text=stats_text, reply_markup=markup)
        await query.answer(lang_texts.get("STATS_UPDATED"))
    except errors.MessageNotModified:
        await query.answer(lang_texts.get("NO_CHANGE_IN_STATS"))
    except Exception as e:
        print(e)
        await query.answer(lang_texts.get("STATS_ERROR"), show_alert=True)