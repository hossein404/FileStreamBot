# WebStreamer/server/panel_routes.py
import asyncio
import aiohttp_jinja2
import secrets
import logging
import os
import re
from aiohttp import web
from urllib.parse import quote_plus, urlencode
from WebStreamer.vars import Var
from WebStreamer.utils.file_properties import get_hash
from WebStreamer.bot.database import *
from WebStreamer.bot.i18n import get_i18n_texts
from .security import verify_password, generate_csrf_token, validate_csrf_token
from WebStreamer.bot.config import config
from pyrogram.errors import UserIsBlocked, InputUserDeactivated, FloodWait
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

routes = web.RouteTableDef()
logger = logging.getLogger("panel_routes")

def parse_buttons(text: str):
    """Parses markdown-style buttons and returns Pyrogram buttons and clean text."""
    pattern = r'\[(.+?)\]\((.+?)\)'
    buttons = []
    
    # Find all button definitions
    matches = re.findall(pattern, text)
    if not matches:
        return text, None
        
    # Create a keyboard row for each button
    keyboard = []
    for match in matches:
        button_text = match[0]
        button_url = match[1]
        keyboard.append([InlineKeyboardButton(button_text, url=button_url)])
    
    # Remove button definitions from the main text
    clean_text = re.sub(pattern, '', text).strip()
    
    return clean_text, InlineKeyboardMarkup(keyboard)

# ... (other routes are the same)

@routes.post("/admin/broadcast", name="admin_broadcast_post")
async def broadcast_post_route(request):
    if not is_admin_logged_in(request): raise web.HTTPForbidden()
    data = await request.post()
    await validate_csrf_token(request, data.get('csrf_token'))
    if not (message_text := data.get('message')): raise web.HTTPBadRequest(text="Message cannot be empty")
    
    clean_text, reply_markup = parse_buttons(message_text)

    bot, user_ids = request.app['bot'], await get_all_user_ids()
    successful_sends, failed_sends = 0, 0
    for user_id in user_ids:
        try:
            await bot.send_message(
                chat_id=user_id, 
                text=clean_text, 
                reply_markup=reply_markup,
                disable_web_page_preview=True
            )
            successful_sends += 1
        except (UserIsBlocked, InputUserDeactivated): failed_sends += 1
        except FloodWait as e: await asyncio.sleep(e.value); await bot.send_message(chat_id=user_id, text=clean_text, reply_markup=reply_markup); successful_sends +=1
        except Exception as e: failed_sends += 1; logger.error(f"Broadcast failed for user {user_id}: {e}")
        await asyncio.sleep(0.1)
        
    lang = await get_panel_context(request)
    success_text = lang['lang'].get("broadcast_success").format(successful_sends=successful_sends, failed_sends=failed_sends)
    redirect_url = f'{request.app.router["admin_broadcast"].url_for()}?token={request.rel_url.query.get("token")}&success_message={quote_plus(success_text)}'
    raise web.HTTPFound(redirect_url)

# ... (the rest of the file remains the same)
# Make sure to copy the entire original file and only replace the broadcast_post_route function
# and add the required imports at the top. For simplicity, I am providing the full file again below.
# (The user should replace the whole file)

# WebStreamer/server/panel_routes.py
import asyncio
import aiohttp_jinja2
import secrets
import logging
import os
import re
from aiohttp import web
from urllib.parse import quote_plus, urlencode
from WebStreamer.vars import Var
from WebStreamer.utils.file_properties import get_hash
from WebStreamer.bot.database import *
from WebStreamer.bot.i18n import get_i18n_texts
from .security import verify_password, generate_csrf_token, validate_csrf_token
from WebStreamer.bot.config import config
from pyrogram.errors import UserIsBlocked, InputUserDeactivated, FloodWait
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

routes = web.RouteTableDef()
logger = logging.getLogger("panel_routes")

def is_admin_logged_in(request):
    return request.rel_url.query.get("token") and request.rel_url.query.get("token") == request.app.get('admin_auth_token')

async def get_panel_context(request):
    lang_code = request.cookies.get("lang", "fa")
    token = request.rel_url.query.get("token")
    return {
        "token": token, "request": request, "current_path": request.path,
        "lang": await get_i18n_texts(lang_code), "current_lang": lang_code,
        "current_path_for_lang_switcher": f"{request.path}?{urlencode({k: v for k, v in request.rel_url.query.items()})}",
        "csrf_token": await generate_csrf_token(request)
    }
def parse_buttons(text: str):
    pattern = r'\[(.+?)\]\((https?://.+?)\)'
    buttons = []
    
    matches = re.findall(pattern, text)
    if not matches:
        return text, None
        
    keyboard = []
    row = []
    for i, match in enumerate(matches):
        button_text = match[0]
        button_url = match[1]
        row.append(InlineKeyboardButton(button_text, url=button_url))
        if len(row) == 2 or i == len(matches) - 1:
            keyboard.append(row)
            row = []

    clean_text = re.sub(pattern, '', text).strip()
    
    return clean_text, InlineKeyboardMarkup(keyboard) if keyboard else None

# --- Login, Logout, Lang ---
@routes.get("/set_lang/{lang_code}", name="set_panel_lang")
async def set_lang_handler(request):
    lang_code = request.match_info.get("lang_code", "fa")
    if lang_code not in ['en', 'fa']: lang_code = 'fa'
    response = web.HTTPFound(request.query.get('return_to', '/admin/dashboard'))
    response.set_cookie("lang", lang_code, max_age=365*24*60*60, path='/')
    return response

@routes.get("/admin", name="admin_redirect")
async def redirect_handler(request):
    url = f'/admin/dashboard?{request.query_string}' if request.query_string else '/admin/dashboard'
    raise web.HTTPFound(url)

@routes.get("/admin/login", name="admin_login")
@aiohttp_jinja2.template('login.html')
async def login_route(request):
    context = await get_panel_context(request)
    context['error'] = request.rel_url.query.get('error')
    return context

@routes.post("/admin/login", name="admin_login_post")
async def login_post_route(request):
    data = await request.post()
    username, password = data.get("username"), data.get("password")
    ip_address = request.headers.get("X-Forwarded-For") or request.remote
    
    success = username == Var.ADMIN_USERNAME and verify_password(password, Var.ADMIN_PASSWORD_HASH)
    await log_login_attempt(ip_address, username, success)

    if success:
        token = secrets.token_hex(32)
        request.app['admin_auth_token'] = token
        await generate_csrf_token(request, new_token=True)
        raise web.HTTPFound(f'/admin/dashboard?token={token}')

    context = await get_panel_context(request)
    context['error'] = context['lang'].get("invalid_credentials")
    return await aiohttp_jinja2.render_template_async('login.html', request, context)

@routes.post("/admin/logout", name="admin_logout")
async def logout_route(request):
    request.app['admin_auth_token'] = None
    raise web.HTTPFound('/admin/login')

# --- Main Panel Routes ---
@routes.get("/admin/dashboard", name="admin_dashboard")
@aiohttp_jinja2.template('dashboard.html')
async def dashboard_route(request):
    if not is_admin_logged_in(request): raise web.HTTPFound(f'/admin/login?error=login_required')
    context = await get_panel_context(request)
    context["stats"] = await get_db_stats_for_panel()
    return context

@routes.get("/admin/users", name="admin_users")
@aiohttp_jinja2.template('users.html')
async def users_list_route(request):
    if not is_admin_logged_in(request): raise web.HTTPFound(f'/admin/login?error=login_required')
    context = await get_panel_context(request)
    search_query = request.rel_url.query.get('q', '')
    context["users"] = await get_all_users_for_panel(search_query)
    context["search_query"] = search_query
    return context

@routes.get("/admin/users/{user_id}", name="admin_user_details")
@aiohttp_jinja2.template('user_details.html')
async def user_details_route(request):
    if not is_admin_logged_in(request): raise web.HTTPFound(f'/admin/login?error=login_required')
    user_id = int(request.match_info['user_id'])
    context = await get_panel_context(request)
    user_details = await get_user_details_for_panel(user_id)
    if not user_details: raise web.HTTPNotFound(text="User not found")
    
    links_data = await get_all_links_for_user(user_id)
    for link in links_data:
        file_hash = get_hash(link['file_unique_id'], Var.HASH_LENGTH)
        link['stream_link'] = f"{Var.URL}{link['id']}/{quote_plus(link['file_name'])}?hash={file_hash}"
        
    context["user"], context["links"] = user_details, links_data
    return context

@routes.get("/admin/users/add", name="admin_add_user")
@aiohttp_jinja2.template('add_user.html')
async def add_user_form(request):
    if not is_admin_logged_in(request): raise web.HTTPFound(f'/admin/login?error=login_required')
    return await get_panel_context(request)
    
@routes.post("/admin/users/add", name="admin_add_user_post")
async def add_user_handler(request):
    if not is_admin_logged_in(request): raise web.HTTPForbidden()
    data = await request.post()
    await validate_csrf_token(request, data.get('csrf_token'))
    try:
        user_id = int(data['user_id'])
        limit_gb = data.get('limit_gb') if data.get('limit_gb') else None
        limit_gb = float(limit_gb) if limit_gb else None
    except (ValueError, TypeError):
        raise web.HTTPBadRequest(text="User ID or traffic limit is invalid.")
    await add_user_by_admin(user_id, limit_gb)
    raise web.HTTPFound(f'/admin/users?token={request.rel_url.query.get("token")}')

@routes.get("/admin/broadcast", name="admin_broadcast")
@aiohttp_jinja2.template('broadcast.html')
async def broadcast_route(request):
    if not is_admin_logged_in(request): raise web.HTTPFound(f'/admin/login?error=login_required')
    context = await get_panel_context(request)
    context['success_message'] = request.rel_url.query.get('success_message')
    return context

@routes.post("/admin/broadcast", name="admin_broadcast_post")
async def broadcast_post_route(request):
    if not is_admin_logged_in(request): raise web.HTTPForbidden()
    data = await request.post()
    await validate_csrf_token(request, data.get('csrf_token'))
    if not (message_text := data.get('message')): raise web.HTTPBadRequest(text="Message cannot be empty")
        
    clean_text, reply_markup = parse_buttons(message_text)
    
    bot, user_ids = request.app['bot'], await get_all_user_ids()
    successful_sends, failed_sends = 0, 0
    for user_id in user_ids:
        try:
            await bot.send_message(
                chat_id=user_id, 
                text=clean_text,
                reply_markup=reply_markup,
                disable_web_page_preview=(reply_markup is None)
            )
            successful_sends += 1
        except (UserIsBlocked, InputUserDeactivated): failed_sends += 1
        except FloodWait as e: await asyncio.sleep(e.value); await bot.send_message(chat_id=user_id, text=clean_text, reply_markup=reply_markup); successful_sends +=1
        except Exception as e: failed_sends += 1; logger.error(f"Broadcast failed for user {user_id}: {e}")
        await asyncio.sleep(0.1)
        
    context = await get_panel_context(request)
    success_text = context['lang'].get("broadcast_success").format(successful_sends=successful_sends, failed_sends=failed_sends)
    redirect_url = f'{request.app.router["admin_broadcast"].url_for()}?token={request.rel_url.query.get("token")}&success_message={quote_plus(success_text)}'
    raise web.HTTPFound(redirect_url)

@routes.get("/admin/settings", name="admin_settings")
@aiohttp_jinja2.template('settings.html')
async def settings_route(request):
    if not is_admin_logged_in(request): raise web.HTTPFound(f'/admin/login?error=login_required')
    context = await get_panel_context(request)
    context['config'] = config
    context['saved'] = request.rel_url.query.get('saved')
    return context

@routes.get("/admin/search_links", name="admin_search_links")
@aiohttp_jinja2.template('search_links.html')
async def search_links_route(request):
    if not is_admin_logged_in(request): raise web.HTTPFound(f'/admin/login?error=login_required')
    context = await get_panel_context(request)
    context.update({
        "links": await search_all_links(request.rel_url.query.get('file_q', ''), request.rel_url.query.get('user_q', ''), request.rel_url.query.get('status', 'active')),
        "search_file_query": request.rel_url.query.get('file_q', ''), "search_user_query": request.rel_url.query.get('user_q', ''),
        "search_status": request.rel_url.query.get('status', 'active'), "deleted": request.rel_url.query.get('deleted')
    })
    return context

@routes.get("/admin/logs", name="admin_server_logs")
@aiohttp_jinja2.template('server_logs.html')
async def server_logs_route(request):
    if not is_admin_logged_in(request): raise web.HTTPFound(f'/admin/login?error=login_required')
    
    logger.info("Admin panel: Server Logs page accessed.")
    context = await get_panel_context(request)
    
    from WebStreamer.__main__ import LOG_FILE_PATH
    
    try:
        if os.path.exists(LOG_FILE_PATH):
            with open(LOG_FILE_PATH, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                if not lines:
                    context['logs'] = "Log file is empty. No activity or errors recorded yet."
                else:
                    context['logs'] = "".join(lines[-200:])
        else:
            context['logs'] = f"Log file not found at path: {LOG_FILE_PATH}"
            
    except Exception as e:
        context['logs'] = f"Error reading log file: {e}"
        
    return context

@routes.get("/admin/security/login_logs", name="admin_login_logs")
@aiohttp_jinja2.template('login_logs.html')
async def login_logs_route(request):
    if not is_admin_logged_in(request): raise web.HTTPFound(f'/admin/login?error=login_required')
    context = await get_panel_context(request)
    context['logs'] = await get_login_attempts(limit=200)
    return context
    
@routes.get("/admin/users/{user_id}/send_message", name="admin_send_message")
@aiohttp_jinja2.template('send_message.html')
async def send_message_route(request):
    if not is_admin_logged_in(request): raise web.HTTPFound(f'/admin/login?error=login_required')
    context = await get_panel_context(request)
    context['user_id'] = request.match_info['user_id']
    return context

# --- POST Actions ---
@routes.post("/admin/action/ban", name="admin_ban_user")
async def ban_user_route(request):
    if not is_admin_logged_in(request): raise web.HTTPForbidden()
    data = await request.post(); await validate_csrf_token(request, data.get('csrf_token'))
    await ban_user(int(data['user_id']))
    raise web.HTTPFound(request.headers.get('Referer', f'/admin/users?token={request.rel_url.query.get("token")}'))

@routes.post("/admin/action/unban", name="admin_unban_user")
async def unban_user_route(request):
    if not is_admin_logged_in(request): raise web.HTTPForbidden()
    data = await request.post(); await validate_csrf_token(request, data.get('csrf_token'))
    await unban_user(int(data['user_id']))
    raise web.HTTPFound(request.headers.get('Referer', f'/admin/users?token={request.rel_url.query.get("token")}'))

@routes.post("/admin/users/update_limit", name="admin_update_limit")
async def update_limit_handler(request):
    if not is_admin_logged_in(request): raise web.HTTPForbidden()
    data = await request.post(); await validate_csrf_token(request, data.get('csrf_token'))
    user_id = int(data['user_id'])
    limit_gb = float(data.get('limit_gb')) if data.get('limit_gb') else None
    await update_user_limit(user_id, limit_gb)
    raise web.HTTPFound(request.headers.get('Referer', f'/admin/users/{user_id}?token={request.rel_url.query.get("token")}'))

@routes.post("/admin/action/delete_link", name="admin_delete_link")
async def delete_link_route(request):
    if not is_admin_logged_in(request): raise web.HTTPForbidden()
    data = await request.post(); await validate_csrf_token(request, data.get('csrf_token'))
    await admin_delete_link(int(data['link_id']))
    raise web.HTTPFound(request.headers.get('Referer', f'/admin/dashboard?token={request.rel_url.query.get("token")}'))

@routes.post("/admin/settings", name="admin_settings_post")
async def settings_post_route(request):
    if not is_admin_logged_in(request): raise web.HTTPForbidden()
    data = await request.post(); await validate_csrf_token(request, data.get('csrf_token'))
    
    for key, value in data.items():
        if key != "csrf_token":
            if key == 'force_sub_channel' and not value:
                value = '0'
            await config.update_setting(key, value)
            
    raise web.HTTPFound(f'/admin/settings?token={request.rel_url.query.get("token")}&saved=true')

@routes.post("/admin/links/deactivate_selected", name="admin_deactivate_selected_links")
async def deactivate_selected_links_route(request):
    if not is_admin_logged_in(request): raise web.HTTPForbidden()
    data = await request.post(); await validate_csrf_token(request, data.get('csrf_token'))
    if link_ids := [int(id) for id in data.getall('link_ids')]: await deactivate_links_by_ids(link_ids)
    redirect_url = f'{request.headers.get("Referer", "/admin/search_links")}?deleted=true'
    raise web.HTTPFound(redirect_url)

@routes.post("/admin/users/{user_id}/deactivate_all", name="admin_deactivate_user_links")
async def deactivate_user_links_route(request):
    if not is_admin_logged_in(request): raise web.HTTPForbidden()
    await validate_csrf_token(request, (await request.post()).get('csrf_token'))
    await deactivate_user_links(int(request.match_info['user_id']))
    raise web.HTTPFound(f'{request.headers.get("Referer")}?deleted=true')

@routes.post("/admin/users/{user_id}/send_message", name="admin_send_message_post")
async def send_message_post_route(request):
    if not is_admin_logged_in(request): raise web.HTTPForbidden()
    user_id = int(request.match_info['user_id']); data = await request.post()
    await validate_csrf_token(request, data.get('csrf_token'))
    context = await get_panel_context(request); context['user_id'] = user_id
    if not (message_text := data.get('message')):
        context['error_message'] = context['lang'].get("message_cannot_be_empty")
    else:
        try: await request.app['bot'].send_message(chat_id=user_id, text=message_text); context['success_message'] = context['lang'].get("message_sent_success")
        except (UserIsBlocked, InputUserDeactivated): context['error_message'] = context['lang'].get("message_sent_fail_blocked")
        except Exception as e: context['error_message'] = context['lang'].get("message_sent_fail_unknown").format(error=e)
    return await aiohttp_jinja2.render_template_async('send_message.html', request, context)

# --- API for Charts ---
@routes.get("/api/stats/daily_uploads", name="api_daily_uploads")
async def daily_uploads_api(request):
    if not is_admin_logged_in(request): raise web.HTTPForbidden()
    stats = await get_daily_uploads_stats(days=7)
    context = await get_panel_context(request)
    return web.json_response({"labels": [s['date'] for s in stats], "data": [s['count'] for s in stats], "label_text": context['lang'].get("new_uploads_chart_label", "New Uploads")})

@routes.get("/api/stats/file_types", name="api_file_types")
async def file_types_api(request):
    if not is_admin_logged_in(request): raise web.HTTPForbidden()
    stats = await get_file_type_stats()
    context = await get_panel_context(request)
    return web.json_response({"labels": [s['file_type'] for s in stats], "data": [s['count'] for s in stats], "label_text": context['lang'].get("file_types_chart_label", "File Types")})

@routes.get("/api/stats/daily_joins", name="api_daily_joins")
async def daily_joins_api(request):
    if not is_admin_logged_in(request): raise web.HTTPForbidden()
    stats = await get_daily_join_stats()
    context = await get_panel_context(request)
    return web.json_response({"labels": [s['date'] for s in stats], "data": [s['count'] for s in stats], "label_text": context['lang'].get("new_users_chart_label", "New Users")})