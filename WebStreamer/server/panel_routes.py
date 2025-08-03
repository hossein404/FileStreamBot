import asyncio
import logging
import os
import re
from urllib.parse import quote_plus

import aiohttp_jinja2
from aiohttp import web
from aiohttp_session import get_session
from pyrogram.errors import FloodWait, InputUserDeactivated, UserIsBlocked
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from WebStreamer.bot.config import config
from WebStreamer.bot.database import (
    add_user_by_admin, admin_delete_link, ban_user, deactivate_links_by_ids,
    deactivate_user_links, get_all_links_for_user, get_all_user_ids,
    get_all_users_for_panel, get_daily_join_stats, get_daily_uploads_stats,
    get_db_stats_for_panel, get_file_type_stats, get_login_attempts,
    get_user_details_for_panel, log_login_attempt, search_all_links,
    unban_user, update_user_limit
)
from WebStreamer.bot.i18n import get_i18n_texts
from WebStreamer.utils.file_properties import get_hash
from WebStreamer.vars import Var
from .security import generate_csrf_token, validate_csrf_token, verify_password

routes = web.RouteTableDef()
logger = logging.getLogger("panel_routes")


# --- Middleware & Context ---

@web.middleware
async def auth_middleware(request: web.Request, handler):
    if request.path.startswith("/admin/") and not request.path.startswith("/admin/login"):
        session = await get_session(request)
        if not session.get("is_admin", False):
            login_url = request.app.router['admin_login'].url_for().with_query(error="login_required")
            raise web.HTTPFound(login_url)
    return await handler(request)

async def get_panel_context(request: web.Request):
    session = await get_session(request)
    lang_code = request.cookies.get("lang", "fa")
    
    generate_csrf_token(session)

    return {
        "request": request,
        "current_path": request.path,
        "lang": await get_i18n_texts(lang_code),
        "current_lang": lang_code,
        "csrf_token": session.get('csrf_token'),
        "current_path_for_lang_switcher": request.path,
    }

def parse_buttons(text: str):
    pattern = r'\[(.+?)\]\((https?://.+?)\)'
    matches = re.findall(pattern, text)
    if not matches:
        return text, None
    keyboard = [[InlineKeyboardButton(text, url=url)] for text, url in matches]
    clean_text = re.sub(pattern, '', text).strip()
    return clean_text, InlineKeyboardMarkup(keyboard) if keyboard else None



# --- Login, Logout & Language Routes ---

@routes.get("/set_lang/{lang_code}", name="set_panel_lang")
async def set_lang_handler(request: web.Request):
    lang_code = request.match_info.get("lang_code", "fa")
    if lang_code not in ['en', 'fa']:
        lang_code = 'fa'
    
    return_to = request.query.get('return_to', str(request.app.router['admin_dashboard'].url_for()))
    response = web.HTTPFound(return_to)
    response.set_cookie("lang", lang_code, max_age=365 * 24 * 60 * 60, path='/')
    return response

@routes.get("/admin", name="admin_redirect")
async def redirect_handler(_: web.Request):
    raise web.HTTPFound('/admin/dashboard')

@routes.get("/admin/login", name="admin_login")
@aiohttp_jinja2.template('login.html')
async def login_route(request: web.Request):
    session = await get_session(request)
    if session.get("is_admin"):
        raise web.HTTPFound(request.app.router['admin_dashboard'].url_for())
    
    context = await get_panel_context(request)
    error_key = request.rel_url.query.get('error')
    if error_key:
        context['error'] = context['lang'].get(error_key, "An unknown error occurred")
    return context

@routes.post("/admin/login", name="admin_login_post")
async def login_post_route(request: web.Request):
    data = await request.post()
    session = await get_session(request)
    
    validate_csrf_token(session, data.get('csrf_token'))
    
    username, password = data.get("username"), data.get("password")
    ip_address = request.headers.get("X-Forwarded-For") or request.remote
    
    success = username == Var.ADMIN_USERNAME and verify_password(password, Var.ADMIN_PASSWORD_HASH)
    await log_login_attempt(ip_address, username, success)

    if success:
        session['is_admin'] = True
        session['username'] = username
        generate_csrf_token(session, new_token=True)
        raise web.HTTPFound(request.app.router['admin_dashboard'].url_for())
    
    login_url = request.app.router['admin_login'].url_for().with_query(error="invalid_credentials")
    raise web.HTTPFound(login_url)

@routes.post("/admin/logout", name="admin_logout")
async def logout_route(request: web.Request):
    session = await get_session(request)
    data = await request.post()
    validate_csrf_token(session, data.get('csrf_token'))
    session.clear()
    raise web.HTTPFound(request.app.router['admin_login'].url_for())


# --- Main Admin Panel Routes ---

@routes.get("/admin/dashboard", name="admin_dashboard")
@aiohttp_jinja2.template('dashboard.html')
async def dashboard_route(request: web.Request):
    context = await get_panel_context(request)
    context["stats"] = await get_db_stats_for_panel()
    return context

# --- User Management Routes ---

@routes.get("/admin/users", name="admin_users")
@aiohttp_jinja2.template('users.html')
async def users_list_route(request: web.Request):
    context = await get_panel_context(request)
    search_query = request.rel_url.query.get('q', '')
    context["users"] = await get_all_users_for_panel(search_query)
    context["search_query"] = search_query
    return context

@routes.get("/admin/users/add", name="admin_add_user")
@aiohttp_jinja2.template('add_user.html')
async def add_user_form(request: web.Request):
    return await get_panel_context(request)

@routes.post("/admin/users/add", name="admin_add_user_post")
async def add_user_handler(request: web.Request):
    data = await request.post()
    session = await get_session(request)
    validate_csrf_token(session, data.get('csrf_token'))
    try:
        user_id = int(data['user_id'])
        limit_gb = float(data['limit_gb']) if data.get('limit_gb') else None
    except (ValueError, TypeError):
        raise web.HTTPBadRequest(text="Invalid User ID or Traffic Limit")
    await add_user_by_admin(user_id, limit_gb)
    raise web.HTTPFound(request.app.router['admin_users'].url_for())

@routes.get("/admin/users/{user_id}", name="admin_user_details")
@aiohttp_jinja2.template('user_details.html')
async def user_details_route(request: web.Request):
    user_id = int(request.match_info['user_id'])
    context = await get_panel_context(request)
    user_details = await get_user_details_for_panel(user_id)
    if not user_details:
        raise web.HTTPNotFound(text="User not found")
    
    links_data = await get_all_links_for_user(user_id)
    for link in links_data:
        file_hash = get_hash(link['file_unique_id'], Var.HASH_LENGTH)
        link['stream_link'] = f"{Var.URL}{link['id']}/{quote_plus(link['file_name'])}?hash={file_hash}"
    
    context["user"] = user_details
    context["links"] = links_data
    return context

@routes.post("/admin/users/update_limit", name="admin_update_limit")
async def update_limit_handler(request: web.Request):
    session = await get_session(request)
    data = await request.post()
    validate_csrf_token(session, data.get('csrf_token'))
    user_id = int(data['user_id'])
    limit_gb = float(data.get('limit_gb')) if data.get('limit_gb') else None
    await update_user_limit(user_id, limit_gb)
    raise web.HTTPFound(request.headers.get('Referer', request.app.router['admin_user_details'].url_for(user_id=str(user_id))))

@routes.post("/admin/action/ban", name="admin_ban_user")
async def ban_user_route(request: web.Request):
    session = await get_session(request)
    data = await request.post()
    validate_csrf_token(session, data.get('csrf_token'))
    await ban_user(int(data['user_id']))
    raise web.HTTPFound(request.headers.get('Referer', request.app.router['admin_users'].url_for()))

@routes.post("/admin/action/unban", name="admin_unban_user")
async def unban_user_route(request: web.Request):
    session = await get_session(request)
    data = await request.post()
    validate_csrf_token(session, data.get('csrf_token'))
    await unban_user(int(data['user_id']))
    raise web.HTTPFound(request.headers.get('Referer', request.app.router['admin_users'].url_for()))

# --- Broadcast & Settings ---

@routes.get("/admin/broadcast", name="admin_broadcast")
@aiohttp_jinja2.template('broadcast.html')
async def broadcast_route(request: web.Request):
    context = await get_panel_context(request)
    context['success_message'] = request.rel_url.query.get('success_message')
    return context

@routes.post("/admin/broadcast", name="admin_broadcast_post")
async def broadcast_post_route(request: web.Request):
    session = await get_session(request)
    data = await request.post()
    validate_csrf_token(session, data.get('csrf_token'))
    
    message_text = data.get('message')
    if not message_text:
        raise web.HTTPBadRequest(text="Message cannot be empty")
        
    clean_text, reply_markup = parse_buttons(message_text)
    bot = request.app['bot']
    user_ids = await get_all_user_ids()
    successful_sends, failed_sends = 0, 0

    for user_id in user_ids:
        try:
            await bot.send_message(
                chat_id=user_id, text=clean_text, reply_markup=reply_markup,
                disable_web_page_preview=(reply_markup is None)
            )
            successful_sends += 1
        except (UserIsBlocked, InputUserDeactivated):
            failed_sends += 1
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await bot.send_message(chat_id=user_id, text=clean_text, reply_markup=reply_markup)
            successful_sends +=1
        except Exception as e:
            failed_sends += 1
            logger.error(f"Broadcast failed for user {user_id}: {e}")
        await asyncio.sleep(0.1)
        
    context = await get_panel_context(request)
    success_text = context['lang'].get("broadcast_success").format(successful_sends=successful_sends, failed_sends=failed_sends)
    redirect_url = request.app.router["admin_broadcast"].url_for().with_query(success_message=quote_plus(success_text))
    raise web.HTTPFound(redirect_url)

@routes.get("/admin/settings", name="admin_settings")
@aiohttp_jinja2.template('settings.html')
async def settings_route(request: web.Request):
    context = await get_panel_context(request)
    context['config'] = config
    context['saved'] = request.rel_url.query.get('saved')
    return context

@routes.post("/admin/settings", name="admin_settings_post")
async def settings_post_route(request: web.Request):
    session = await get_session(request)
    data = await request.post()
    validate_csrf_token(session, data.get('csrf_token'))
    
    for key, value in data.items():
        if key == "csrf_token": continue
        if key == 'force_sub_channel' and not value: value = '0'
        await config.update_setting(key, value)
            
    raise web.HTTPFound(request.app.router['admin_settings'].url_for().with_query(saved='true'))

# --- Links and Logs ---

@routes.get("/admin/search_links", name="admin_search_links")
@aiohttp_jinja2.template('search_links.html')
async def search_links_route(request: web.Request):
    context = await get_panel_context(request)
    context.update({
        "links": await search_all_links(request.rel_url.query.get('file_q', ''), request.rel_url.query.get('user_q', ''), request.rel_url.query.get('status', 'active')),
        "search_file_query": request.rel_url.query.get('file_q', ''), "search_user_query": request.rel_url.query.get('user_q', ''),
        "search_status": request.rel_url.query.get('status', 'active'), "deleted": request.rel_url.query.get('deleted')
    })
    return context

@routes.post("/admin/links/deactivate_selected", name="admin_deactivate_selected_links")
async def deactivate_selected_links_route(request: web.Request):
    session = await get_session(request)
    data = await request.post()
    validate_csrf_token(session, data.get('csrf_token'))
    if link_ids := [int(id) for id in data.getall('link_ids')]:
        await deactivate_links_by_ids(link_ids)
    raise web.HTTPFound(request.headers.get("Referer", "/admin/search_links"))


@routes.get("/admin/logs", name="admin_server_logs")
@aiohttp_jinja2.template('server_logs.html')
async def server_logs_route(request: web.Request):
    context = await get_panel_context(request)
    from WebStreamer.__main__ import LOG_FILE_PATH
    try:
        if os.path.exists(LOG_FILE_PATH):
            with open(LOG_FILE_PATH, 'r', encoding='utf-8') as f:
                context['logs'] = "".join(f.readlines()[-200:])
        else:
            context['logs'] = f"Log file not found at path: {LOG_FILE_PATH}"
    except Exception as e:
        context['logs'] = f"Error reading log file: {e}"
    return context

@routes.get("/admin/security/login_logs", name="admin_login_logs")
@aiohttp_jinja2.template('login_logs.html')
async def login_logs_route(request: web.Request):
    context = await get_panel_context(request)
    context['logs'] = await get_login_attempts(limit=200)
    return context

@routes.get("/admin/users/{user_id}/send_message", name="admin_send_message")
@aiohttp_jinja2.template('send_message.html')
async def send_message_route(request: web.Request):
    context = await get_panel_context(request)
    context['user_id'] = request.match_info['user_id']
    return context

@routes.post("/admin/users/{user_id}/send_message", name="admin_send_message_post")
async def send_message_post_route(request: web.Request):
    session = await get_session(request)
    user_id = int(request.match_info['user_id'])
    data = await request.post()
    validate_csrf_token(session, data.get('csrf_token'))
    context = await get_panel_context(request)
    context['user_id'] = user_id
    
    message_text = data.get('message')
    if not message_text:
        context['error_message'] = context['lang'].get("message_cannot_be_empty")
    else:
        try:
            await request.app['bot'].send_message(chat_id=user_id, text=message_text)
            context['success_message'] = context['lang'].get("message_sent_success")
        except (UserIsBlocked, InputUserDeactivated):
            context['error_message'] = context['lang'].get("message_sent_fail_blocked")
        except Exception as e:
            context['error_message'] = context['lang'].get("message_sent_fail_unknown").format(error=e)
            
    return await aiohttp_jinja2.render_template_async('send_message.html', request, context)


@routes.post("/admin/action/delete_link", name="admin_delete_link")
async def delete_link_route(request: web.Request):
    session = await get_session(request)
    data = await request.post()
    validate_csrf_token(session, data.get('csrf_token'))
    await admin_delete_link(int(data['link_id']))
    raise web.HTTPFound(request.headers.get('Referer', request.app.router['admin_dashboard'].url_for()))

@routes.post("/admin/users/{user_id}/deactivate_all", name="admin_deactivate_user_links")
async def deactivate_user_links_route(request: web.Request):
    session = await get_session(request)
    data = await request.post()
    validate_csrf_token(session, data.get('csrf_token'))
    await deactivate_user_links(int(request.match_info['user_id']))
    raise web.HTTPFound(f'{request.headers.get("Referer")}?deleted=true')

# --- API Routes for Charts ---

@routes.get("/api/stats/daily_uploads", name="api_daily_uploads")
async def daily_uploads_api(request: web.Request):
    context = await get_panel_context(request)
    stats = await get_daily_uploads_stats(days=7)
    return web.json_response({
        "labels": [s['date'] for s in stats], 
        "data": [s['count'] for s in stats], 
        "label_text": context['lang'].get("new_uploads_chart_label", "New Uploads")
    })

@routes.get("/api/stats/file_types", name="api_file_types")
async def file_types_api(request: web.Request):
    context = await get_panel_context(request)
    stats = await get_file_type_stats()
    return web.json_response({
        "labels": [s['file_type'] for s in stats], 
        "data": [s['count'] for s in stats], 
        "label_text": context['lang'].get("file_types_chart_label", "File Types")
    })

@routes.get("/api/stats/daily_joins", name="api_daily_joins")
async def daily_joins_api(request: web.Request):
    context = await get_panel_context(request)
    stats = await get_daily_join_stats()
    return web.json_response({
        "labels": [s['date'] for s in stats], 
        "data": [s['count'] for s in stats], 
        "label_text": context['lang'].get("new_users_chart_label", "New Users")
    })