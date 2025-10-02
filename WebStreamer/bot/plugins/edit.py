# WebStreamer/bot/plugins/edit.py
import re
import datetime
from pyrogram import filters
from pyrogram.types import Message
from WebStreamer.bot import StreamBot
from WebStreamer.bot.database import update_link_details
from WebStreamer.bot.i18n import get_i18n_texts

@StreamBot.on_message(filters.command("edit") & filters.private)
async def edit_link_handler(bot: StreamBot, m: Message):
    lang_texts = await get_i18n_texts(m.from_user.id)
    
    if not m.reply_to_message:
        await m.reply_text(lang_texts.get("EDIT_COMMAND_USAGE").format(command="/edit /p <password> /e <hours>"))
        return

    link_id = None
    if m.reply_to_message.reply_markup:
        for row in m.reply_to_message.reply_markup.inline_keyboard:
            for button in row:
                if button.callback_data and button.callback_data.startswith("copy_"):
                    link_id = int(button.callback_data.split("_")[1])
                    break
            if link_id:
                break
    
    if not link_id and m.reply_to_message.entities:
        for entity in m.reply_to_message.entities:
            if entity.type.name == "TEXT_LINK":
                match = re.search(r'/(\d+)/', entity.url)
                if match:
                    link_id = int(match.group(1))
                    break
    
    if not link_id:
        await m.reply_text(lang_texts.get("EDIT_COMMAND_USAGE").format(command="/edit /p <password> /e <hours>"))
        return

    user_id = m.from_user.id
    command_text = m.text.strip()
    
    password = None
    expiry_hours = None

    password_match = re.search(r'/p (\S+)', command_text)
    if password_match:
        password = password_match.group(1)

    expiry_match = re.search(r'/e (\d+)', command_text)
    if expiry_match:
        expiry_hours = int(expiry_match.group(1))
        
    if not password and not expiry_hours:
        await m.reply_text(lang_texts.get("EDIT_NO_CHANGES"))
        return
        
    if expiry_hours:
        expiry_date = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=expiry_hours)
    else:
        expiry_date = None

    success = await update_link_details(link_id, user_id, password, expiry_date)
    
    if not success:
        await m.reply_text(lang_texts.get("EDIT_NOT_OWNER"))
        return

    changes_list = []
    if password:
        changes_list.append(lang_texts.get("EDIT_PASSWORD_SET").format(password=password))
    if expiry_hours:
        changes_list.append(lang_texts.get("EDIT_EXPIRY_SET").format(hours=expiry_hours))
        
    confirmation_text = lang_texts.get("EDIT_SUCCESS").format(changes="\n".join(changes_list))
    
    await m.reply_text(confirmation_text)
