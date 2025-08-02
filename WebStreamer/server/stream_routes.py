# WebStreamer/server/stream_routes.py
import re
import time
import math
import logging
import mimetypes
import asyncio
from aiohttp import web
from urllib.parse import unquote_plus
from aiohttp.http_exceptions import BadStatusLine
from WebStreamer.bot import multi_clients, work_loads
from WebStreamer.errors import FIleNotFound, InvalidHash
from WebStreamer import Var, utils, StartTime, __version__, StreamBot
from WebStreamer.bot.database import is_link_active, increment_link_views

logger = logging.getLogger("routes")
routes = web.RouteTableDef()
class_cache = {}

@routes.get("/", allow_head=True)
async def root_route_handler(_):
    return web.json_response(
        {
            "server_status": "running", "uptime": utils.get_readable_time(time.time() - StartTime),
            "telegram_bot": "@" + StreamBot.username, "version": f"v{__version__}",
        }
    )

@routes.get(r"/{path:.+}", allow_head=True)
async def stream_handler(request: web.Request):
    try:
        path = request.match_info["path"]
        secure_hash = request.rel_url.query.get("hash")
        
        if '/' in path:
            message_id_str, filename_encoded = path.split('/', 1)
            message_id = int(message_id_str)
            custom_filename = unquote_plus(filename_encoded)
        else:
            message_id = int(path)
            custom_filename = None
        
        if not secure_hash:
            raise InvalidHash("Hash parameter is missing or invalid.")

        if not await is_link_active(message_id):
            return web.Response(status=410, text="410 Gone: This link has been deleted or has expired.")

        # Increment view count in the background
        asyncio.create_task(increment_link_views(message_id))

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


async def media_streamer(request: web.Request, message_id: int, secure_hash: str, custom_filename: str = None):
    range_header = request.headers.get("Range", 0)
    index = min(work_loads, key=work_loads.get)
    faster_client = multi_clients[index]
    
    tg_connect = class_cache.get(faster_client, utils.ByteStreamer(faster_client))
    if faster_client not in class_cache: class_cache[faster_client] = tg_connect
        
    file_id = await tg_connect.get_file_properties(message_id)
    
    if utils.get_hash(file_id.unique_id, Var.HASH_LENGTH) != secure_hash:
        raise InvalidHash
    
    file_name = custom_filename or utils.get_name(file_id)
    file_name = file_name.replace("\r", "").replace("\n", " ").strip()
    file_size = file_id.file_size
    
    mime_type = file_id.mime_type or mimetypes.guess_type(file_name)[0] or "application/octet-stream"
    
    from_bytes, until_bytes = (0, file_size -1)
    if range_header:
        from_bytes, until_bytes = [int(i) for i in range_header.replace("bytes=", "").split("-") if i]
        until_bytes = until_bytes or file_size - 1

    if (until_bytes > file_size) or (from_bytes < 0) or (until_bytes < from_bytes):
        return web.Response(status=416, body="416: Range not satisfiable", headers={"Content-Range": f"bytes */{file_size}"})

    chunk_size = 1024 * 1024
    offset = from_bytes - (from_bytes % chunk_size)
    first_part_cut = from_bytes - offset
    last_part_cut = (until_bytes % chunk_size) + 1
    part_count = math.ceil((until_bytes - offset + 1) / chunk_size)
    req_length = until_bytes - from_bytes + 1

    body = tg_connect.yield_file(file_id, index, offset, first_part_cut, last_part_cut, part_count, chunk_size)

    return web.Response(
        status=206 if range_header else 200,
        body=body,
        headers={
            "Content-Type": mime_type,
            "Content-Range": f"bytes {from_bytes}-{until_bytes}/{file_size}",
            "Content-Length": str(req_length),
            "Content-Disposition": f'{"inline" if "video/" in mime_type or "audio/" in mime_type else "attachment"}; filename="{file_name}"',
            "Accept-Ranges": "bytes",
        }
    )