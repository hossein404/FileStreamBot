import re
import time
import math
import logging
import mimetypes
from aiohttp import web
from urllib.parse import unquote_plus
from aiohttp.http_exceptions import BadStatusLine
from WebStreamer.bot import multi_clients, work_loads
from WebStreamer.errors import FIleNotFound, InvalidHash
from WebStreamer import Var, utils, StartTime, __version__, StreamBot
from WebStreamer.bot.database import is_link_active

logger = logging.getLogger("routes")


routes = web.RouteTableDef()

@routes.get("/", allow_head=True)
async def root_route_handler(_):
    return web.json_response(
        {
            "server_status": "running",
            "uptime": utils.get_readable_time(time.time() - StartTime),
            "telegram_bot": "@" + StreamBot.username,
            "connected_bots": len(multi_clients),
            "loads": dict(
                ("bot" + str(c + 1), l)
                for c, (_, l) in enumerate(
                    sorted(work_loads.items(), key=lambda x: x[1], reverse=True)
                )
            ),
            "version": f"v{__version__}",
        }
    )


@routes.get(r"/{path:.+}", allow_head=True)
async def stream_handler(request: web.Request):
    try:
        path = request.match_info["path"]
        
        # Check for short link format: /<hash><message_id>
        short_link_match = re.search(r"^([0-9a-f]{%s})(\d+)$" % (Var.HASH_LENGTH), path)
        if short_link_match:
            secure_hash = short_link_match.group(1)
            message_id = int(short_link_match.group(2))
            custom_filename = None
        else:
            # For other formats, hash must be in query
            secure_hash = request.rel_url.query.get("hash")
            if not secure_hash:
                raise InvalidHash("Hash parameter is missing or invalid.")

            # Check for new format with custom name: /<message_id>/<filename>
            if '/' in path:
                message_id_str, filename_encoded = path.split('/', 1)
                message_id = int(message_id_str)
                custom_filename = unquote_plus(filename_encoded)
            # Check for old format: /<message_id>
            else:
                message_id = int(path)
                custom_filename = None
        
        # Security Check: Ensure the link is active in the database
        if not await is_link_active(message_id):
            return web.Response(status=410, text="410 Gone: This link has been deleted or has expired.")

        return await media_streamer(request, message_id, secure_hash, custom_filename)

    except InvalidHash as e:
        raise web.HTTPForbidden(text=str(e))
    except FIleNotFound as e:
        raise web.HTTPNotFound(text=str(e))
    except (ValueError, ConnectionResetError, BadStatusLine):
        raise web.HTTPBadRequest(text="Invalid request format.")
    except Exception as e:
        logger.critical(str(e), exc_info=True)
        raise web.HTTPInternalServerError(text=str(e))


class_cache = {}

async def media_streamer(request: web.Request, message_id: int, secure_hash: str, custom_filename: str = None):
    range_header = request.headers.get("Range", 0)
    
    index = min(work_loads, key=work_loads.get)
    faster_client = multi_clients[index]
    
    if Var.MULTI_CLIENT:
        logger.info(f"Client {index} is now serving {request.remote}")

    if faster_client in class_cache:
        tg_connect = class_cache[faster_client]
    else:
        tg_connect = utils.ByteStreamer(faster_client)
        class_cache[faster_client] = tg_connect
        
    file_id = await tg_connect.get_file_properties(message_id)
    
    if utils.get_hash(file_id.unique_id, Var.HASH_LENGTH) != secure_hash:
        logger.debug(f"Invalid hash for message with ID {message_id}")
        raise InvalidHash
    
    # Use custom filename from URL if present, otherwise get original name
    if custom_filename:
        file_name = custom_filename
    else:
        file_name = utils.get_name(file_id)

    # Sanitize filename to prevent HTTP Header Injection
    file_name = file_name.replace("\r", "").replace("\n", " ").strip()

    file_size = file_id.file_size
    mime_type = file_id.mime_type
    if not mime_type:
        mime_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"

    if range_header:
        from_bytes, until_bytes = range_header.replace("bytes=", "").split("-")
        from_bytes = int(from_bytes)
        until_bytes = int(until_bytes) if until_bytes else file_size - 1
    else:
        from_bytes = request.http_range.start or 0
        until_bytes = (request.http_range.stop or file_size) - 1

    if (until_bytes > file_size) or (from_bytes < 0) or (until_bytes < from_bytes):
        return web.Response(
            status=416,
            body="416: Range not satisfiable",
            headers={"Content-Range": f"bytes */{file_size}"},
        )

    chunk_size = 1024 * 1024
    until_bytes = min(until_bytes, file_size - 1)

    offset = from_bytes - (from_bytes % chunk_size)
    first_part_cut = from_bytes - offset
    last_part_cut = until_bytes % chunk_size + 1
    req_length = until_bytes - from_bytes + 1
    part_count = math.ceil(until_bytes / chunk_size) - math.floor(offset / chunk_size)

    body = tg_connect.yield_file(
        file_id, index, offset, first_part_cut, last_part_cut, part_count, chunk_size
    )

    # --- بخش اصلاح شده ---
    # به طور پیش‌فرض، فایل برای دانلود ارسال می‌شود
    disposition = "attachment"
    
    # اگر نوع فایل ویدیو یا صوت بود، آن را برای پخش آنلاین (استریم) تنظیم می‌کنیم
    if isinstance(mime_type, str) and ("video/" in mime_type or "audio/" in mime_type):
        disposition = "inline"
    # --- پایان بخش اصلاح شده ---

    return web.Response(
        status=206 if range_header else 200,
        body=body,
        headers={
            "Content-Type": mime_type,
            "Content-Range": f"bytes {from_bytes}-{until_bytes}/{file_size}",
            "Content-Length": str(req_length),
            "Content-Disposition": f'{disposition}; filename="{file_name}"',
            "Accept-Ranges": "bytes",
        },
    )
