# WebStreamer/server/panel_routes.py
import asyncio
import aiohttp_jinja2
import secrets
import logging
from aiohttp import web
from urllib.parse import quote_plus, urlencode
from WebStreamer.vars import Var
from WebStreamer.utils.file_properties import get_hash
from WebStreamer.bot.database import (
    get_db_stats_for_panel, get_all_users_for_panel, get_user_details_for_panel,
    get_all_links_for_user, ban_user, unban_user, admin_delete_link,
    get_all_user_ids, get_daily_join_stats, add_user_by_admin, update_user_limit
)
from WebStreamer.bot.i18n import get_i18n_texts
from .security import verify_password, generate_csrf_token, validate_csrf_token
from pyrogram.errors import UserIsBlocked, InputUserDeactivated

routes = web.RouteTableDef()
logger = logging.getLogger("panel_routes")


def is_admin_logged_in(request):
    token = request.rel_url.query.get("token")
    return token and token == request.app.get('admin_auth_token')

async def get_panel_context(request):
    lang_code = request.cookies.get("lang", "fa")
    token = request.rel_url.query.get("token")
    csrf_token = await generate_csrf_token(request)
    new_query = {k: v for k, v in request.rel_url.query.items()}
    query_string = urlencode(new_query)
    current_path_for_lang_switcher = f"{request.path}?{query_string}" if query_string else request.path

    return {
        "token": token,
        "request": request,
        "current_path": request.path,
        "lang": await get_i18n_texts(lang_code),
        "current_lang": lang_code,
        "current_path_for_lang_switcher": current_path_for_lang_switcher,
        "csrf_token": csrf_token
    }

@routes.get("/set_lang/{lang_code}", name="set_panel_lang")
async def set_lang_handler(request):
    lang_code = request.match_info.get("lang_code", "fa")
    if lang_code not in ['en', 'fa']:
        lang_code = 'fa'
    return_to = request.query.get('return_to', '/admin/dashboard')
    response = web.HTTPFound(return_to)
    response.set_cookie("lang", lang_code, max_age=365*24*60*60, path='/')
    return response

@routes.get("/admin", name="admin_redirect")
async def redirect_handler(request):
    token = request.rel_url.query.get("token")
    url = '/admin/dashboard'
    if token:
        url += f'?token={token}'
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
    username = data.get("username")
    password = data.get("password")
    
    is_valid_password = verify_password(password, Var.ADMIN_PASSWORD_HASH)

    if username == Var.ADMIN_USERNAME and is_valid_password:
        token = secrets.token_hex(32)
        request.app['admin_auth_token'] = token
        await generate_csrf_token(request, new_token=True)
        raise web.HTTPFound(f'/admin/dashboard?token={token}')

    context = await get_panel_context(request)
    context['error'] = context['lang'].get("invalid_credentials")
    return await aiohttp_jinja2.render_template_async('login.html', request, context)


@routes.get("/admin/dashboard", name="admin_dashboard")
@aiohttp_jinja2.template('dashboard.html')
async def dashboard_route(request):
    if not is_admin_logged_in(request):
        context = await get_panel_context(request)
        raise web.HTTPFound(f'/admin/login?error={context["lang"].get("login_required")}')
    context = await get_panel_context(request)
    context["stats"] = await get_db_stats_for_panel()
    return context

@routes.post("/admin/users/add", name="admin_add_user_post")
async def add_user_handler(request):
    if not is_admin_logged_in(request):
        raise web.HTTPForbidden()
    data = await request.post()
    await validate_csrf_token(request, data.get('csrf_token'))
    try:
        user_id = int(data['user_id'])
        limit_gb = data.get('limit_gb')
        limit_gb = float(limit_gb) if limit_gb else None
    except (ValueError, TypeError):
        raise web.HTTPBadRequest(text="User ID or traffic limit is invalid.")
    await add_user_by_admin(user_id, limit_gb)
    raise web.HTTPFound(f'/admin/users?token={request.rel_url.query.get("token")}')

@routes.get("/admin/users", name="admin_users")
@aiohttp_jinja2.template('users.html')
async def users_list_route(request):
    if not is_admin_logged_in(request):
        context = await get_panel_context(request)
        raise web.HTTPFound(f'/admin/login?error={context["lang"].get("login_required")}')
    context = await get_panel_context(request)
    search_query = request.rel_url.query.get('q', '')
    context["users"] = await get_all_users_for_panel(search_query)
    context["search_query"] = search_query
    return context

@routes.get("/admin/users/add", name="admin_add_user")
@aiohttp_jinja2.template('add_user.html')
async def add_user_form(request):
    if not is_admin_logged_in(request):
        context = await get_panel_context(request)
        raise web.HTTPFound(f'/admin/login?error={context["lang"].get("login_required")}')
    return await get_panel_context(request)
    
@routes.get("/admin/users/{user_id}", name="admin_user_details")
@aiohttp_jinja2.template('user_details.html')
async def user_details_route(request):
    if not is_admin_logged_in(request):
        context = await get_panel_context(request)
        raise web.HTTPFound(f'/admin/login?error={context["lang"].get("login_required")}')
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
async def update_limit_handler(request):
    if not is_admin_logged_in(request):
        raise web.HTTPForbidden()
    data = await request.post()
    await validate_csrf_token(request, data.get('csrf_token'))
    try:
        user_id = int(data['user_id'])
        limit_gb = data.get('limit_gb')
        limit_gb = float(limit_gb) if limit_gb else None
    except (ValueError, TypeError):
        raise web.HTTPBadRequest(text="User ID or traffic limit is invalid.")
    await update_user_limit(user_id, limit_gb)
    redirect_url = request.headers.get('Referer', f'/admin/users/{user_id}?token={request.rel_url.query.get("token")}')
    raise web.HTTPFound(redirect_url)

@routes.post("/admin/action/ban", name="admin_ban_user")
async def ban_user_route(request):
    if not is_admin_logged_in(request):
        raise web.HTTPForbidden()
    data = await request.post()
    await validate_csrf_token(request, data.get('csrf_token'))
    user_id = int(data['user_id'])
    await ban_user(user_id)
    redirect_url = request.headers.get('Referer', f'/admin/users?token={request.rel_url.query.get("token")}')
    raise web.HTTPFound(redirect_url)

@routes.post("/admin/action/unban", name="admin_unban_user")
async def unban_user_route(request):
    if not is_admin_logged_in(request):
        raise web.HTTPForbidden()
    data = await request.post()
    await validate_csrf_token(request, data.get('csrf_token'))
    user_id = int(data['user_id'])
    await unban_user(user_id)
    redirect_url = request.headers.get('Referer', f'/admin/users?token={request.rel_url.query.get("token")}')
    raise web.HTTPFound(redirect_url)

@routes.post("/admin/action/delete_link", name="admin_delete_link")
async def delete_link_route(request):
    if not is_admin_logged_in(request):
        raise web.HTTPForbidden()
    data = await request.post()
    await validate_csrf_token(request, data.get('csrf_token'))
    link_id = int(data['link_id'])
    await admin_delete_link(link_id)
    redirect_url = request.headers.get('Referer', f'/admin/dashboard?token={request.rel_url.query.get("token")}')
    raise web.HTTPFound(redirect_url)

@routes.get("/admin/broadcast", name="admin_broadcast")
@aiohttp_jinja2.template('broadcast.html')
async def broadcast_route(request):
    if not is_admin_logged_in(request):
        context = await get_panel_context(request)
        raise web.HTTPFound(f'/admin/login?error={context["lang"].get("login_required")}')
    return await get_panel_context(request)

@routes.post("/admin/broadcast", name="admin_broadcast_post")
async def broadcast_post_route(request):
    if not is_admin_logged_in(request):
        raise web.HTTPForbidden()
    data = await request.post()
    await validate_csrf_token(request, data.get('csrf_token'))
    message_text = data.get('message')
    if not message_text:
        raise web.HTTPBadRequest(text="Message cannot be empty")
    bot = request.app['bot']
    user_ids = await get_all_user_ids()
    successful_sends = 0
    failed_sends = 0
    for user_id in user_ids:
        try:
            await bot.send_message(chat_id=user_id, text=message_text)
            successful_sends += 1
        except (UserIsBlocked, InputUserDeactivated):
            failed_sends += 1
        except Exception as e:
            failed_sends += 1
            logger.error(f"Broadcast failed for user {user_id}: {e}")
        await asyncio.sleep(0.1)
    context = await get_panel_context(request)
    context['success_message'] = f"Message sent to {successful_sends} users. {failed_sends} failed."
    return await aiohttp_jinja2.render_template_async('broadcast.html', request, context)

@routes.get("/api/stats/daily_joins", name="api_daily_joins")
async def daily_joins_api(request):
    if not is_admin_logged_in(request):
        raise web.HTTPForbidden()
    stats = await get_daily_join_stats()
    context = await get_panel_context(request)
    labels = [s['date'] for s in stats]
    data = [s['count'] for s in stats]
    return web.json_response({
        "labels": labels, 
        "data": data,
        "label_text": context['lang'].get("new_users_chart_label", "New Users")
    })

@routes.post("/admin/logout", name="admin_logout")
async def logout_route(request):
    request.app['admin_auth_token'] = None
    raise web.HTTPFound('/admin/login')