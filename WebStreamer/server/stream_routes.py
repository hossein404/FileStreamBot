# WebStreamer/server/stream_routes.py
import re
import os
import time
import math
import logging
import mimetypes
import asyncio
import datetime
from typing import Tuple, Optional, Any

from aiohttp import web
from urllib.parse import unquote_plus, quote
from aiohttp.http_exceptions import BadStatusLine
from email.utils import format_datetime, parsedate_to_datetime

from WebStreamer.bot import multi_clients, work_loads
from WebStreamer.errors import FIleNotFound, InvalidHash
from WebStreamer import Var, utils, StartTime, __version__, StreamBot
from WebStreamer.bot.database import get_link_with_owner_info, increment_link_views

import aiohttp_jinja2

logger = logging.getLogger("routes")
routes = web.RouteTableDef()
class_cache = {}


def _prepare_disposition_filename(file_name: str) -> tuple[str, str]:
    """Return sanitized UTF-8 and ASCII fallback names for Content-Disposition."""

    cleaned = file_name.replace("\x00", "")
    cleaned = cleaned.replace('"', "")
    cleaned = cleaned.replace("/", " ").replace("\\", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = cleaned or "file"

    ascii_fallback = cleaned.encode("ascii", "ignore").decode("ascii", "ignore")
    ascii_fallback = ascii_fallback.replace("/", " ").replace("\\", " ")
    ascii_fallback = re.sub(r"\s+", " ", ascii_fallback).strip()

    original_ext = os.path.splitext(cleaned)[1]
    fallback_ext = os.path.splitext(ascii_fallback)[1]
    if original_ext and fallback_ext.lower() != original_ext.lower():
        ascii_root = os.path.splitext(ascii_fallback)[0]
        ascii_fallback = (ascii_root or ascii_fallback or "file") + original_ext

    if not ascii_fallback:
        ascii_fallback = ("file" + original_ext) if original_ext else "file"

    return cleaned, ascii_fallback


def _build_content_disposition_header(disposition_type: str, filenames: tuple[str, str]) -> str:
    utf8_filename, ascii_fallback = filenames
    header_value = f"{disposition_type}; filename=\"{ascii_fallback}\""
    header_value += f"; filename*=UTF-8''{quote(utf8_filename)}"
    return header_value


def _parse_range_header(range_header: str, file_size: int) -> Tuple[int, int, bool]:
    """Parse a RFC7233 range header.

    Returns a tuple of ``(from_bytes, until_bytes, is_partial)``. ``is_partial`` is
    ``True`` when the client explicitly requested a subset of the file.

    Raises ``ValueError`` for malformed or unsatisfiable ranges.
    """

    if not range_header:
        return 0, file_size - 1, False

    try:
        unit, range_spec = range_header.strip().split("=", 1)
    except ValueError as exc:  # pragma: no cover - defensive guard
        raise ValueError("Invalid Range header format") from exc

    if unit.lower() != "bytes":
        raise ValueError("Only bytes Range unit is supported")

    ranges = range_spec.split(",")
    if len(ranges) != 1:
        raise ValueError("Multiple ranges are not supported")

    start_str, end_str = ranges[0].strip().split("-", 1)

    if start_str:
        start = int(start_str)
        if start >= file_size:
            raise ValueError("Range start out of bounds")
    else:
        start = None

    if end_str:
        end = int(end_str)
    else:
        end = None

    if start is None and end is None:
        raise ValueError("Empty range specifier")

    if start is None:
        # suffix-byte-range-spec. e.g. bytes=-500 (last 500 bytes)
        suffix_length = end + 1
        if suffix_length <= 0:
            raise ValueError("Invalid suffix length in Range header")
        start = max(file_size - suffix_length, 0)
        end = file_size - 1
    else:
        if end is None or end >= file_size:
            end = file_size - 1

    if start < 0 or end < start:
        raise ValueError("Invalid byte range")

    return start, end, True


def _etag_matches(header_value: str, current_etag: str) -> bool:
    if not header_value:
        return False

    header_value = header_value.strip()
    if header_value == "*":
        return True

    for part in header_value.split(","):
        candidate = part.strip()
        if not candidate:
            continue
        if candidate.startswith("W/"):
            candidate = candidate[2:].strip()
        if candidate == current_etag:
            return True
    return False


def _coerce_datetime(value: Any) -> Optional[datetime.datetime]:
    if isinstance(value, datetime.datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _format_http_datetime(dt: datetime.datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    else:
        dt = dt.astimezone(datetime.timezone.utc)
    return format_datetime(dt, usegmt=True)


def _parse_http_datetime(header_value: Optional[str]) -> Optional[datetime.datetime]:
    if not header_value:
        return None

    try:
        parsed = parsedate_to_datetime(header_value)
    except (TypeError, ValueError, IndexError):
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed.astimezone(datetime.timezone.utc)


def _normalize_to_utc(dt: datetime.datetime) -> datetime.datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc)


def _if_range_allows_partial(if_range_value: str, current_etag: str, last_modified: Optional[datetime.datetime]) -> bool:
    if not if_range_value:
        return True

    candidate = if_range_value.strip()
    if not candidate or candidate.startswith("W/"):
        return False

    if candidate.startswith('"') and candidate.endswith('"'):
        return candidate == current_etag

    if last_modified is None:
        return False

    try:
        parsed = parsedate_to_datetime(candidate)
    except (TypeError, ValueError, IndexError):
        return False

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)

    if last_modified.tzinfo is None:
        reference = last_modified.replace(tzinfo=datetime.timezone.utc)
    else:
        reference = last_modified.astimezone(datetime.timezone.utc)

    return reference <= parsed


def _prepare_not_modified_headers(base_headers: dict[str, str]) -> dict[str, str]:
    filtered = {k: v for k, v in base_headers.items() if k not in {"Content-Type", "Content-Length"}}
    return filtered

@routes.get("/", allow_head=True)
async def root_route_handler(_):
    return web.json_response(
        {
            "server_status": "running", "uptime": utils.get_readable_time(time.time() - StartTime),
            "telegram_bot": "@" + StreamBot.username, "version": f"v{__version__}",
        }
    )

@routes.get(r"/{path:.+}", allow_head=True)
@routes.post(r"/{path:.+}")
async def stream_handler(request: web.Request):
    try:
        path = request.match_info["path"]
        
        if '/' in path:
            message_id_str, filename_encoded = path.split('/', 1)
            message_id = int(message_id_str)
            custom_filename = unquote_plus(filename_encoded)
        else:
            message_id = int(path)
            custom_filename = None
        
        secure_hash = request.rel_url.query.get("hash")
        if not secure_hash:
            raise InvalidHash("Hash parameter is missing or invalid.")

        link_info = await get_link_with_owner_info(message_id)
        if not link_info:
            return web.Response(status=404, text="404 Not Found: Link does not exist.")

        if not link_info['is_active'] or link_info['is_banned']:
            return web.Response(status=410, text="410 Gone: This link has been deleted or the owner is banned.")

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        expiry_value = link_info.get('expiry_date')
        expiry_dt = _coerce_datetime(expiry_value) if expiry_value else None
        if expiry_dt:
            expiry_dt = _normalize_to_utc(expiry_dt)
            link_info['expiry_date'] = expiry_dt
            if now_utc > expiry_dt:
                return web.Response(status=410, text="410 Gone: This link has expired.")

        if link_info['password']:
            password_from_user = None
            if request.method == "POST":
                data = await request.post()
                password_from_user = data.get("password")
            
            if password_from_user != link_info['password']:
                context = {"request": request, "message_id": message_id, "file_name": custom_filename}
                if password_from_user is not None: 
                    context["error"] = "Incorrect password"
                return await aiohttp_jinja2.render_template_async('password.html', request, context)

        asyncio.create_task(increment_link_views(message_id))

        return await media_streamer(request, message_id, secure_hash, custom_filename, link_info)

    except (ConnectionError, ConnectionResetError, asyncio.CancelledError):
        logger.info("Client connection closed unexpectedly. This is normal for media streaming.")
        return web.Response(status=200)
    except InvalidHash as e:
        raise web.HTTPForbidden(text=str(e))
    except FIleNotFound as e:
        raise web.HTTPNotFound(text=str(e))
    except (ValueError, BadStatusLine):
        raise web.HTTPBadRequest(text="Invalid request format.")
    except Exception as e:
        logger.critical(f"Unhandled error in stream_handler: {e}", exc_info=True)
        raise web.HTTPInternalServerError(text=str(e))


async def media_streamer(
    request: web.Request,
    message_id: int,
    secure_hash: str,
    custom_filename: str = None,
    link_info: Optional[dict] = None,
):
    index = min(work_loads, key=work_loads.get)
    faster_client = multi_clients[index]
    
    tg_connect = class_cache.get(faster_client, utils.ByteStreamer(faster_client))
    if faster_client not in class_cache: class_cache[faster_client] = tg_connect
        
    file_id = await tg_connect.get_file_properties(message_id)
    
    if utils.get_hash(file_id.unique_id, Var.HASH_LENGTH) != secure_hash:
        raise InvalidHash
    
    file_name = custom_filename or utils.get_name(file_id)
    file_name = file_name.replace("\r", " ").replace("\n", " ").strip()
    file_name = re.sub(r"\s+", " ", file_name)
    file_size = file_id.file_size

    mime_type = file_id.mime_type or mimetypes.guess_type(file_name)[0] or "application/octet-stream"

    etag_value = f'"{file_id.unique_id}"'
    last_modified_dt = _coerce_datetime(link_info.get("creation_date") if link_info else None)
    last_modified_header = _format_http_datetime(last_modified_dt) if last_modified_dt else None

    disposition_type = "inline" if "video/" in mime_type or "audio/" in mime_type else "attachment"
    sanitized_filename = _prepare_disposition_filename(file_name)
    content_disposition = _build_content_disposition_header(disposition_type, sanitized_filename)

    base_headers = {
        "Content-Type": mime_type,
        "Content-Disposition": content_disposition,
        "Accept-Ranges": "bytes",
        "Connection": "keep-alive",
        "ETag": etag_value,
        "Cache-Control": "public, max-age=3600",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
    }
    if last_modified_header:
        base_headers["Last-Modified"] = last_modified_header

    if_none_match = request.headers.get("If-None-Match")

    last_modified_utc = _normalize_to_utc(last_modified_dt) if last_modified_dt else None

    if last_modified_utc:
        if_unmodified_since = _parse_http_datetime(request.headers.get("If-Unmodified-Since"))
        if if_unmodified_since and if_unmodified_since < last_modified_utc:
            error_headers = {
                "ETag": etag_value,
                "Cache-Control": base_headers["Cache-Control"],
                "X-Content-Type-Options": base_headers["X-Content-Type-Options"],
                "Content-Type": "text/plain; charset=utf-8",
            }
            if last_modified_header:
                error_headers["Last-Modified"] = last_modified_header
            return web.Response(status=412, text="412: Precondition Failed", headers=error_headers)

    if if_none_match and _etag_matches(if_none_match, etag_value):
        return web.Response(status=304, headers=_prepare_not_modified_headers(base_headers))

    if last_modified_utc and not if_none_match:
        if_modified_since = _parse_http_datetime(request.headers.get("If-Modified-Since"))
        if if_modified_since and if_modified_since >= last_modified_utc:
            not_modified_headers = _prepare_not_modified_headers(base_headers)
            return web.Response(status=304, headers=not_modified_headers)

    range_header = request.headers.get("Range")
    if_range_header = request.headers.get("If-Range")

    if range_header and _if_range_allows_partial(if_range_header, etag_value, last_modified_dt):
        try:
            from_bytes, until_bytes, is_partial = _parse_range_header(range_header, file_size)
        except ValueError:
            error_headers = dict(base_headers)
            error_headers["Content-Range"] = f"bytes */{file_size}"
            error_headers["Content-Type"] = "text/plain; charset=utf-8"
            return web.Response(
                status=416,
                body="416: Range not satisfiable",
                headers=error_headers,
            )
    else:
        from_bytes, until_bytes, is_partial = 0, file_size - 1, False

    req_length = max(until_bytes - from_bytes + 1, 0)

    chunk_size = 1024 * 1024
    offset = from_bytes - (from_bytes % chunk_size)
    first_part_cut = from_bytes - offset
    span = max(until_bytes - offset + 1, 0)
    part_count = math.ceil(span / chunk_size) if span else 0
    last_part_cut = (until_bytes % chunk_size) + 1 if part_count else 0

    if part_count == 0:
        error_headers = dict(base_headers)
        error_headers["Content-Range"] = f"bytes */{file_size}"
        error_headers["Content-Type"] = "text/plain; charset=utf-8"
        return web.Response(
            status=416,
            body="416: Range not satisfiable",
            headers=error_headers,
        )

    body = tg_connect.yield_file(file_id, index, offset, first_part_cut, last_part_cut, part_count, chunk_size)

    headers = dict(base_headers)
    headers["Content-Length"] = str(req_length)

    if is_partial:
        headers["Content-Range"] = f"bytes {from_bytes}-{until_bytes}/{file_size}"

    status_code = 206 if is_partial else 200

    if request.method == "HEAD":
        return web.Response(status=status_code, headers=headers)

    resp = web.StreamResponse(status=status_code, headers=headers)
    await resp.prepare(request)

    async for chunk in body:
        try:
            await resp.write(chunk)
            await resp.drain()
        except (ConnectionResetError, asyncio.CancelledError):
            break

    try:
        await resp.write_eof()
    except (ConnectionResetError, asyncio.CancelledError):
        pass

    return resp
