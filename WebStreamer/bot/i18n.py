# WebStreamer/bot/i18n.py
import sqlite3
import asyncio

# --- دیکشنری ترجمه‌ها (نسخه کامل و نهایی) ---
translations = {
    'fa': {
        # --- ربات تلگرام ---
        "START_TEXT": "👋 **سلام {mention} عزیز!**\n\nمن ربات استریم فایل هستم. هر فایلی رو برام بفرستی، در یک چشم به هم زدن لینک مستقیمش رو بهت تحویل میدم. 🚀\n\n**قابلیت‌های ربات:**\n» با دستور /mylinks می‌تونی لینک‌هات رو مدیریت و حذف کنی.\n» با دستور /stats می‌تونی وضعیت حسابت رو ببینی.",
        "START_FOOTER": "\nبرای شروع، یک فایل رو **فوروارد** یا **آپلود** کن.",
        "RATE_LIMIT_INFO": "» برای جلوگیری از اسپم، شما می‌توانید `{max_requests}` فایل در هر `{time_window}` ثانیه ارسال کنید.\n",
        "DEVELOPER_BUTTON": "👨‍💻 توسعه‌دهنده",
        "LANGUAGE_CHANGED": "زبان با موفقیت تغییر کرد!",
        "NOT_AUTHORIZED": "شما اجازه استفاده از این ربات را ندارید. لطفاً با ادمین تماس بگیرید.",
        "BANNED_USER_ERROR": "شما توسط ادمین مسدود شده‌اید و اجازه استفاده از ربات را ندارید.",
        "TRAFFIC_LIMIT_EXCEEDED": "🚫 **حجم شما تمام شده است!**\n\nشما تمامِ حجم اختصاص یافته ({traffic_limit_gb} GB) را مصرف کرده‌اید. برای تمدید با ادمین تماس بگیرید.",
        "RATE_LIMIT_ERROR": "🐢 **شما بیش از حد درخواست داده‌اید!**\n\nلطفاً `{time_window}` ثانیه صبر کنید و دوباره تلاش کنید.",
        "LINK_GENERATED": "✅ **لینک شما با موفقیت ساخته شد!**\n\n📂 **نام فایل:** `{final_filename}`\n⚖️ **حجم فایل:** `{file_size_in_mb:.2f} MB`",
        "OPEN_LINK_BUTTON": "🚀 باز کردن لینک",
        "COPY_LINK_BUTTON": "📋 کپی لینک",
        "LINK_COPIED_SUCCESS": "لینک در پیام جدید برای شما ارسال شد.",
        "LINK_COPIED_MESSAGE": "👇 لینک شما برای کپی آسان:\n\n`{stream_link}`",
        "COPY_ERROR": "خطا! امکان بازیابی لینک وجود ندارد.",
        "MYLINKS_HEADER": "🔗 **لینک‌های شما**\n\nبرای حذف هر لینک، روی آن کلیک کنید.",
        "NO_LINKS_YET": "شما هنوز هیچ لینکی نساخته‌اید. یک فایل برای من بفرستید!",
        "DELETE_BUTTON_TEXT": "🗑️ {file_name} ({file_size_mb:.2f} MB)",
        "PREVIOUS_BUTTON": "قبلی",
        "NEXT_BUTTON": "بعدی",
        "SAME_PAGE_NOTICE": "شما در همین صفحه هستید.",
        "LINK_DELETED_SUCCESS": "لینک با موفقیت حذف و غیرفعال شد!",
        "ALL_LINKS_DELETED": "✅ تمام لینک‌های شما حذف شدند.",
        "ACCOUNT_STATS_HEADER": "وضعیت حساب شما",
        "TOTAL_FILES": "تعداد کل فایل‌ها: `{file_count}`",
        "TRAFFIC_STATS_HEADER": "آمار ترافیک",
        "USED_TRAFFIC": "مصرف شده: `{used_gb:.2f} GB`",
        "TOTAL_LIMIT": "محدودیت کل: `{limit_str}`",
        "REMAINING_TRAFFIC": "باقی‌مانده: `{remaining_str}`",
        "USAGE_PROGRESS": "میزان مصرف:\n{progress_text}",
        "UNLIMITED": "نامحدود",
        "REFRESH_BUTTON": "بروزرسانی",
        "STATS_UPDATED": "آمار بروزرسانی شد!",
        "NO_CHANGE_IN_STATS": "تغییری در آمار شما وجود ندارد.",
        "STATS_ERROR": "خطایی رخ داد!",

        # --- پنل مدیریت (کامل شده) ---
        "admin_panel": "پنل مدیریت",
        "dashboard": "داشبورد",
        "users": "کاربران",
        "broadcast": "پیام همگانی",
        "logout": "خروج",
        "login_title": "ورود به پنل مدیریت",
        "username": "نام کاربری",
        "password": "رمز عبور",
        "login_button": "ورود",
        "invalid_credentials": "نام کاربری یا رمز عبور نامعتبر است",
        "login_required": "برای دسترسی به این صفحه باید وارد شوید",
        "dashboard_header": "داشبورد",
        "dashboard_subheader": "آمار کلی ربات شما",
        "total_users": "تعداد کل کاربران",
        "active_links": "لینک‌های فعال",
        "total_traffic": "ترافیک مصرفی",
        "new_users_chart_title": "کاربران جدید در ۷ روز گذشته",
        "new_users_chart_label": "تعداد کاربران جدید",
        "add_user_title": "افزودن کاربر جدید",
        "back_to_users_list": "بازگشت به لیست کاربران",
        "add_user_header": "افزودن کاربر جدید",
        "add_user_subheader": "یک کاربر جدید را به لیست کاربران مجاز اضافه کنید.",
        "user_numeric_id": "ID عددی کاربر:",
        "user_id_placeholder": "مثال: 123456789",
        "user_id_help_text": "کاربر می‌تواند ID خود را از ربات‌هایی مثل @userinfobot دریافت کند.",
        "traffic_limit_gb": "محدودیت حجم (GB):",
        "traffic_limit_placeholder": "برای حجم نامحدود، این فیلد را خالی بگذارید",
        "add_user_button": "افزودن کاربر",
        "users_list_header": "لیست کاربران",
        "users_list_subheader": "جستجو، مدیریت و افزودن کاربران جدید.",
        "search_placeholder": "جستجو بر اساس ID، نام یا نام کاربری...",
        "search_button": "جستجو",
        "table_header_user": "کاربر",
        "table_header_usage_limit": "مصرف / محدودیت (GB)",
        "table_header_join_date": "تاریخ عضویت",
        "table_header_status": "وضعیت",
        "table_header_actions": "عملیات",
        "status_banned": "مسدود",
        "status_active": "فعال",
        "action_details": "جزئیات",
        "action_ban": "مسدود کردن",
        "action_unban": "رفع مسدودیت",
        "no_users_found": "هیچ کاربری یافت نشد.",
        "broadcast_header": "پیام همگانی (Broadcast)",
        "broadcast_subheader": "ارسال پیام به تمام کاربران فعال ربات.",
        "message_text_label": "متن پیام:",
        "message_placeholder": "پیام خود را اینجا بنویسید...",
        "send_message_button": "ارسال پیام",
        "broadcast_success": "پیام با موفقیت به {successful_sends} کاربر ارسال شد. {failed_sends} ارسال ناموفق بود.",
    },
    'en': {
        # --- Telegram Bot ---
        "START_TEXT": "👋 **Hi {mention}!**\n\nI am a file streaming bot. Send me any file, and I'll give you a direct link in a flash. 🚀\n\n**Bot Features:**\n» Use /mylinks to manage and delete your links.\n» Use /stats to see your account status.",
        "START_FOOTER": "\nTo get started, **forward** or **upload** a file.",
        "RATE_LIMIT_INFO": "» To prevent spam, you can send `{max_requests}` files every `{time_window}` seconds.\n",
        "DEVELOPER_BUTTON": "👨‍💻 Developer",
        "LANGUAGE_CHANGED": "Language changed successfully!",
        "NOT_AUTHORIZED": "You are not authorized to use this bot. Please contact the admin.",
        "BANNED_USER_ERROR": "You have been banned by the admin and are not allowed to use the bot.",
        "TRAFFIC_LIMIT_EXCEEDED": "🚫 **You have run out of data!**\n\nYou have used all of your allocated data ({traffic_limit_gb} GB). Please contact the admin to renew.",
        "RATE_LIMIT_ERROR": "🐢 **You are making too many requests!**\n\nPlease wait for `{time_window}` seconds and try again.",
        "LINK_GENERATED": "✅ **Your link was created successfully!**\n\n📂 **File Name:** `{final_filename}`\n⚖️ **File Size:** `{file_size_in_mb:.2f} MB`",
        "OPEN_LINK_BUTTON": "🚀 Open Link",
        "COPY_LINK_BUTTON": "📋 Copy Link",
        "LINK_COPIED_SUCCESS": "The link has been sent to you in a new message.",
        "LINK_COPIED_MESSAGE": "👇 Your link for easy copying:\n\n`{stream_link}`",
        "COPY_ERROR": "Error! The link could not be retrieved.",
        "MYLINKS_HEADER": "🔗 **Your Links**\n\nTo delete a link, just click on it.",
        "NO_LINKS_YET": "You haven't created any links yet. Send me a file to start!",
        "DELETE_BUTTON_TEXT": "🗑️ {file_name} ({file_size_mb:.2f} MB)",
        "PREVIOUS_BUTTON": "Previous",
        "NEXT_BUTTON": "Next",
        "SAME_PAGE_NOTICE": "You are already on this page.",
        "LINK_DELETED_SUCCESS": "Link was successfully deleted and deactivated!",
        "ALL_LINKS_DELETED": "✅ All your links have been deleted.",
        "ACCOUNT_STATS_HEADER": "Your Account Status",
        "TOTAL_FILES": "Total Files: `{file_count}`",
        "TRAFFIC_STATS_HEADER": "Traffic Stats",
        "USED_TRAFFIC": "Used: `{used_gb:.2f} GB`",
        "TOTAL_LIMIT": "Total Limit: `{limit_str}`",
        "REMAINING_TRAFFIC": "Remaining: `{remaining_str}`",
        "USAGE_PROGRESS": "Usage Progress:\n{progress_text}",
        "UNLIMITED": "Unlimited",
        "REFRESH_BUTTON": "Refresh",
        "STATS_UPDATED": "Stats updated!",
        "NO_CHANGE_IN_STATS": "There is no change in your stats.",
        "STATS_ERROR": "An error occurred!",

        # --- Admin Panel (Completed) ---
        "admin_panel": "Admin Panel",
        "dashboard": "Dashboard",
        "users": "Users",
        "broadcast": "Broadcast",
        "logout": "Logout",
        "login_title": "Admin Panel Login",
        "username": "Username",
        "password": "Password",
        "login_button": "Login",
        "invalid_credentials": "Invalid username or password",
        "login_required": "You must be logged in to access this page",
        "dashboard_header": "Dashboard",
        "dashboard_subheader": "Overall statistics of your bot",
        "total_users": "Total Users",
        "active_links": "Active Links",
        "total_traffic": "Total Traffic",
        "new_users_chart_title": "New Users in the Last 7 Days",
        "new_users_chart_label": "Number of New Users",
        "add_user_title": "Add New User",
        "back_to_users_list": "Back to Users List",
        "add_user_header": "Add New User",
        "add_user_subheader": "Add a new user to the list of authorized users.",
        "user_numeric_id": "User Numeric ID:",
        "user_id_placeholder": "Example: 123456789",
        "user_id_help_text": "The user can get their ID from bots like @userinfobot.",
        "traffic_limit_gb": "Traffic Limit (GB):",
        "traffic_limit_placeholder": "Leave empty for unlimited traffic",
        "add_user_button": "Add User",
        "users_list_header": "Users List",
        "users_list_subheader": "Search, manage, and add new users.",
        "search_placeholder": "Search by ID, name, or username...",
        "search_button": "Search",
        "table_header_user": "User",
        "table_header_usage_limit": "Usage / Limit (GB)",
        "table_header_join_date": "Join Date",
        "table_header_status": "Status",
        "table_header_actions": "Actions",
        "status_banned": "Banned",
        "status_active": "Active",
        "action_details": "Details",
        "action_ban": "Ban",
        "action_unban": "Unban",
        "no_users_found": "No users found.",
        "broadcast_header": "Broadcast Message",
        "broadcast_subheader": "Send a message to all active bot users.",
        "message_text_label": "Message Text:",
        "message_placeholder": "Write your message here...",
        "send_message_button": "Send Message",
        "broadcast_success": "Message sent successfully to {successful_sends} users. {failed_sends} failed.",
    }
}


DB_PATH = 'database.sqlite3'
user_lang_cache = {}
lock = asyncio.Lock()

async def get_user_lang(user_id: int) -> str:
    """Gets user language from cache or DB asynchronously."""
    async with lock:
        if user_id in user_lang_cache:
            return user_lang_cache[user_id]
        
        try:
            # Using synchronous sqlite3 for simplicity in this context
            con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
            cur = con.cursor()
            cur.execute("SELECT language FROM users WHERE id = ?", (user_id,))
            row = cur.fetchone()
            con.close()
            lang = row[0] if row and row[0] else 'fa'
            user_lang_cache[user_id] = lang
            return lang
        except Exception:
            return 'fa'

async def get_i18n_texts(user_id_or_lang_code: str | int) -> dict:
    """
    Returns the translation dictionary for a given user ID or language code.
    Defaults to English if the requested language is not found.
    """
    if isinstance(user_id_or_lang_code, str):
        lang = user_id_or_lang_code
    else:
        lang = await get_user_lang(user_id_or_lang_code)
    
    return translations.get(lang, translations['en'])