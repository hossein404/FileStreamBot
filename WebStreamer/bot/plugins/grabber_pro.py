# ultimate_grabber_pro.py
# Grab + Fast DL + Upload + Clean links (alnum-only) + Persian UI

import asyncio, json, math, os, re, shutil, tempfile, uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse, quote_plus

import yt_dlp
from pyrogram import filters, errors
from pyrogram.enums import ParseMode, MessagesFilter
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# --- project imports ---
from WebStreamer.bot import StreamBot
from WebStreamer.vars import Var
from WebStreamer.bot.i18n import get_i18n_texts
from WebStreamer.bot.utils import check_user_is_member
from WebStreamer.bot.database import (
    is_user_banned, is_user_authorized, get_user_traffic_details,
    update_stats, insert_link
)
from WebStreamer.utils import get_hash
from WebStreamer.utils.file_properties import parse_file_unique_id

# ================= Settings =================
GRAB_COOKIES = os.getenv("GRAB_COOKIES", "/etc/filestreambot/cookies.txt")
GRAB_PROXY = os.getenv("GRAB_PROXY", "").strip()
GRAB_REFERER = os.getenv("GRAB_REFERER", "").strip()
GRAB_HEADERS_JSON = os.getenv("GRAB_HEADERS_JSON", "").strip()
GRAB_GEO = os.getenv("GRAB_GEO", "US")
PAGE_SIZE = int(os.getenv("GRAB_PAGE_SIZE", "8"))

# به‌صورت صریح int تا اگر "2.0" بود هم خطا ندهد
MAX_CONC = int(float(os.getenv("GRAB_MAX_CONDLS", "3")))
RETRIES = int(float(os.getenv("GRAB_RETRIES", "6")))
BACKOFF = int(float(os.getenv("GRAB_BACKOFF_BASE", "2")))

REUSE_LIMIT = int(os.getenv("REUSE_BIN_SEARCH_LIMIT", "120"))
MAX_TG_MB = getattr(Var, "MAX_TG_UPLOAD_MB", 1900)

URL_RE = re.compile(r"(https?://[^\s]+)")
JOBS: Dict[str, Dict[str, Any]] = {}
JOB_SEM = asyncio.Semaphore(MAX_CONC)

# ================= Helpers =================
def fmt_bytes(n: Optional[float]) -> str:
    if not n or n <= 0:
        return "نامشخص"
    u = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while n >= 1024 and i < len(u) - 1:
        n /= 1024.0
        i += 1
    return f"{n:.2f} {u[i]}"

def fmt_dur(s: Optional[float]) -> str:
    if not s or s <= 0:
        return "—"
    s = int(s)
    h = s // 3600
    m = (s % 3600) // 60
    ss = s % 60
    return f"{h:02d}:{m:02d}:{ss:02d}" if h else f"{m:02d}:{ss:02d}"

def safe_text(t: str, lim: int = 128) -> str:
    t = (t or "").replace("<", "").replace(">", "").strip()
    return t[:lim] if len(t) > lim else t

async def safe_edit(m: Message, t: str):
    try:
        await m.edit_text(t, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    except Exception:
        pass

# حروف و علائم فارسی → لاتین برای لینک
_FA2EN_MAP = {
    "ا": "a", "آ": "a", "ب": "b", "پ": "p", "ت": "t", "ث": "s", "ج": "j",
    "چ": "ch", "ح": "h", "خ": "kh", "د": "d", "ذ": "z", "ر": "r", "ز": "z",
    "ژ": "zh", "س": "s", "ش": "sh", "ص": "s", "ض": "z", "ط": "t", "ظ": "z",
    "ع": "a", "غ": "gh", "ف": "f", "ق": "gh", "ک": "k", "ك": "k", "گ": "g",
    "ل": "l", "م": "m", "ن": "n", "و": "v", "ه": "h", "ی": "y", "ي": "y",
    "‌": " ", "ٔ": "", "ً": "", "ٌ": "", "ٍ": "", "َ": "", "ُ": "", "ِ": "",
    "ّ": "", "ء": "", "ٔ": "", "ـ": " ",
    " ": " "
}
def fa_to_en(s: str) -> str:
    if not s:
        return ""
    out = []
    for ch in s:
        out.append(_FA2EN_MAP.get(ch, ch))
    return "".join(out)

# نام فایل محلی (فارسـی/انگلیسی/اعداد مجاز)، بدون underscore
BAD_FS = r'[\\/:*?"<>|`]'
def clean_local_filename(name: str, fallback: str = "file.bin", max_len: int = 100) -> str:
    import unicodedata
    name = unicodedata.normalize("NFKC", (name or "").strip())
    # اسلش‌های یونیکد/مورّب و ... → فاصله
    for ch in ("/", "\\", "⧸", "\u2215", "\u2044"):
        name = name.replace(ch, " ")
    # حذف underscore طبق خواسته
    name = name.replace("_", " ")
    # فضا را یکی کن
    name = re.sub(r"\s+", " ", name)
    # کاراکترهای خطرناک
    name = re.sub(BAD_FS, "-", name)
    # کاراکترهای کنترل
    name = re.sub(r"[\x00-\x1f]", "", name)
    # خط تیره‌ی پشت‌سرهم
    name = re.sub(r"-{2,}", "-", name).strip(" .-")
    if not name:
        name = fallback
    stem, ext = os.path.splitext(name)
    # طول
    if len(name) > max_len:
        keep = max_len - len(ext)
        stem = stem[:max(1, keep)].rstrip(" .-")
        name = (stem or "file") + ext
    return name

# نام مخصوص لینک: فقط حروف/اعداد انگلیسی (پسوند حفظ می‌شود)
def alnum_link_name(name: str, fallback: str = "file.bin", max_len: int = 90) -> str:
    stem, ext = os.path.splitext(name or "")
    if not ext:
        ext = ".bin"
    # ترنسلیت فارسی → انگلیسی
    stem = fa_to_en(stem)
    # فقط A-Za-z0-9
    stem = re.sub(r"[^A-Za-z0-9]+", "", stem)
    if not stem:
        stem = "file"
    stem = stem[:max_len]
    return stem + ext

def build_headers(url: str) -> Dict[str, str]:
    headers = {"User-Agent": "Mozilla/5.0"}
    if GRAB_REFERER:
        headers["Referer"] = GRAB_REFERER
    else:
        try:
            up = urlparse(url)
            headers["Referer"] = f"{up.scheme}://{up.netloc}/"
        except Exception:
            pass
    if GRAB_HEADERS_JSON:
        try:
            extra = json.loads(GRAB_HEADERS_JSON)
            if isinstance(extra, dict):
                headers.update({str(k): str(v) for k, v in extra.items()})
        except Exception:
            pass
    return headers

def ydl_base_opts(url_for_headers: str = "") -> Dict[str, Any]:
    opts: Dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "retries": 10,
        "fragment_retries": 15,
        "file_access_retries": 10,
        "force_ipv4": True,
        "geo_bypass": True,
        "geo_bypass_country": GRAB_GEO,
        "http_headers": build_headers(url_for_headers),
        "socket_timeout": 30,
        "concurrent_fragment_downloads": 8,    # موازی
        "http_chunk_size": 10 * 1024 * 1024,   # 10MB
        "buffersize": 64 * 1024,
    }
    # اگر aria2c نصب بود، سرعت چندبرابر می‌شود
    if shutil.which("aria2c"):
        opts["external_downloader"] = "aria2c"
        opts["external_downloader_args"] = ["-x16", "-s16", "-k5M", "-m5", "--min-split-size=5M"]
    if os.path.exists(GRAB_COOKIES):
        opts["cookiefile"] = GRAB_COOKIES
    if GRAB_PROXY:
        opts["proxy"] = GRAB_PROXY
    return opts

# ================= Data models =================
@dataclass
class VideoItem:
    title: str
    url: str
    duration: Optional[float]
    id: str

@dataclass
class FormatChoice:
    format_id: str
    ext: str
    resolution: str
    fps: Optional[int]
    vcodec: str
    acodec: str
    filesize: Optional[int]

# ================= Extraction =================
def extract_items(page_url: str) -> List[VideoItem]:
    base = ydl_base_opts(page_url)
    base["skip_download"] = True
    with yt_dlp.YoutubeDL(base) as ydl:
        info = ydl.extract_info(page_url, download=False)

    items: List[VideoItem] = []

    def add(ii: Dict[str, Any]):
        if not ii:
            return
        items.append(
            VideoItem(
                title=ii.get("title") or ii.get("id") or "ویدئو",
                url=ii.get("webpage_url") or ii.get("url") or page_url,
                duration=ii.get("duration"),
                id=ii.get("id") or uuid.uuid4().hex[:8],
            )
        )

    if info.get("_type") == "playlist" and info.get("entries"):
        for e in info["entries"]:
            add(e)
    else:
        add(info)

    # dedup
    seen = set()
    out: List[VideoItem] = []
    for it in items:
        key = (it.url, it.id)
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out

def extract_formats(video_url: str) -> Tuple[Dict[str, Any], List[FormatChoice]]:
    base = ydl_base_opts(video_url)
    base["skip_download"] = True
    with yt_dlp.YoutubeDL(base) as ydl:
        info = ydl.extract_info(video_url, download=False)

    fmts = info.get("formats") or []
    choices: List[FormatChoice] = []
    for f in fmts:
        ext = (f.get("ext") or "").lower()
        if ext in ("mhtml", "jpg", "png", "webp"):
            continue
        res = f"{(f.get('height') or '')}p" if f.get("height") else (f.get("resolution") or "")
        choices.append(
            FormatChoice(
                format_id=str(f.get("format_id")),
                ext=ext,
                resolution=res,
                fps=f.get("fps"),
                vcodec=f.get("vcodec") or "",
                acodec=f.get("acodec") or "",
                filesize=f.get("filesize") or f.get("filesize_approx"),
            )
        )

    # sort by resolution desc, then preference for mp4/avc/m4a
    def key(c: FormatChoice):
        try:
            h = int(re.sub(r"\D", "", c.resolution) or 0)
        except Exception:
            h = 0
        pref = (1 if c.ext == "mp4" else 0) + (1 if "avc" in c.vcodec else 0) + (1 if "m4a" in c.acodec else 0)
        return (h, pref, (c.filesize or 0))

    choices.sort(key=key, reverse=True)
    return info, choices

# ================= Download =================
def download_with_ytdlp(video_url: str, fmt: "FormatChoice", outdir: str, subs: bool) -> Dict[str, Any]:
    # اگر فرمت ترکیبی باشد (video+audio)، merge لازم است
    need_merge = "+" in (fmt.format_id or "")
    outtmpl = os.path.join(outdir, "%(title).200B-%(id)s.%(ext)s")
    opts = ydl_base_opts(video_url)
    opts.update({
        "format": fmt.format_id,            # دقیقاً همان فرمت انتخابی کاربر
        "outtmpl": outtmpl,
        "noprogress": True,
        "restrictfilenames": False,         # نام انسانی؛ بعداً پاک‌سازی می‌کنیم
        "postprocessors": [],               # هیچ تبدیلی بی‌دلیل
        "merge_output_format": "mp4" if need_merge else None,
        "prefer_ffmpeg": True
    })
    if subs:
        opts["writesubtitles"] = True
        opts["subtitleslangs"] = ["fa", "Farsi", "fa-ir", "en", "best"]
        opts["embedsubtitles"] = True

    tries = max(1, RETRIES)
    last = None
    for i in range(1, tries + 1):
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(video_url, download=True)
        except Exception as e:
            last = e
            if i == tries:
                break
            import time
            time.sleep(BACKOFF * i)
    raise last or RuntimeError("download failed")

def determine_path(dl_info: Dict[str, Any], outdir: str) -> str:
    if dl_info.get("requested_downloads"):
        p = dl_info["requested_downloads"][0].get("filepath")
        if p and os.path.exists(p):
            return p
    with yt_dlp.YoutubeDL({"quiet": True, "outtmpl": os.path.join(outdir, "%(title).200B-%(id)s.%(ext)s")}) as y2:
        return y2.prepare_filename(dl_info)

# ================= BIN & direct link =================
async def search_in_bin(client: StreamBot, file_name: str, file_size: int):
    try:
        async for msg in client.search_messages(
            Var.BIN_CHANNEL, query=file_name, filter=MessagesFilter.DOCUMENT, limit=REUSE_LIMIT
        ):
            if not msg or not msg.document:
                continue
            n = msg.document.file_name or ""
            s = msg.document.file_size or 0
            if ((n == file_name) or (file_name.lower() in n.lower())) and file_size and s and abs(s - file_size) <= max(
                1_048_576, int(0.01 * file_size)
            ):
                return msg
    except Exception:
        pass
    return None

async def send_stream_link(client: StreamBot, user_id: int, bin_msg, local_name: str):
    link_name = alnum_link_name(local_name)
    try:
        fid = await parse_file_unique_id(bin_msg)
    except Exception:
        fid = None
    try:
        h = get_hash(fid, Var.HASH_LENGTH) if fid else ""
        link = f"{Var.URL}{bin_msg.id}/{quote_plus(link_name)}?hash={h}"
    except Exception:
        link = None
    if link:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("باز کردن لینک", url=link)]])
        await client.send_message(user_id, f"🔗 لینک مستقیم فایل:\n{link}", reply_markup=kb, disable_web_page_preview=True)

async def send_to_user(client: StreamBot, user_id: int, file_obj: Any, fname: str, local: bool = False):
    ext = fname.lower().rsplit(".", 1)[-1] if "." in fname else ""
    try:
        if ext in ["mp4", "mkv", "mov", "webm"]:
            await client.send_video(user_id, file_obj, caption=fname)
        elif ext in ["mp3", "m4a", "aac", "flac", "wav", "ogg"]:
            await client.send_audio(user_id, file_obj, caption=fname)
        else:
            await client.send_document(user_id, file_obj, caption=fname)
    except Exception:
        await client.send_document(user_id, file_obj, caption=fname)

async def upload_and_link(client: StreamBot, user_id: int, filepath: str, status: Message, as_doc: bool):
    size_mb = os.path.getsize(filepath) / (1024 * 1024)
    if size_mb > MAX_TG_MB:
        await safe_edit(status, f"❌ فایل خیلی بزرگ است (~{int(size_mb)} MB).")
        return
    fname = os.path.basename(filepath)

    # استفاده مجدد از BIN اگر موجود بود
    reuse = await search_in_bin(client, fname, os.path.getsize(filepath))
    if reuse:
        await safe_edit(status, "✅ فایل قبلاً وجود داشت؛ ارسال بدون آپلود…")
        if as_doc:
            await client.send_document(user_id, reuse.document.file_id, caption=fname)
        else:
            ext = fname.lower().rsplit(".", 1)[-1] if "." in fname else ""
            if ext in ["mp4", "mkv", "mov", "webm"]:
                await client.send_video(user_id, reuse.document.file_id, caption=fname)
            elif ext in ["mp3", "m4a", "aac", "flac", "wav", "ogg"]:
                await client.send_audio(user_id, reuse.document.file_id, caption=fname)
            else:
                await client.send_document(user_id, reuse.document.file_id, caption=fname)
        await send_stream_link(client, user_id, reuse, fname)
        try:
            await status.delete()
        except Exception:
            pass
        return

    await safe_edit(status, "⬆️ آپلود به BIN_CHANNEL …")
    bin_msg = await client.send_document(Var.BIN_CHANNEL, filepath, caption=fname)

    try:
        fid = await parse_file_unique_id(bin_msg)
    except Exception:
        fid = None
    try:
        await insert_link(user_id, bin_msg.id, fname, size_mb, fid, None, None)
    except Exception:
        pass

    await safe_edit(status, "⬆️ ارسال به شما …")
    if as_doc:
        await client.send_document(user_id, filepath, caption=fname)
    else:
        await send_to_user(client, user_id, filepath, fname, local=True)

    await send_stream_link(client, user_id, bin_msg, fname)
    try:
        await status.delete()
    except Exception:
        pass
    try:
        await update_stats(user_id, size_mb)
    except Exception:
        pass

# ================= Keyboards =================
def kb_items(job_id: str, items: List[VideoItem], page: int) -> InlineKeyboardMarkup:
    pages = max(1, math.ceil(len(items) / PAGE_SIZE))
    s = page * PAGE_SIZE
    e = min(len(items), s + PAGE_SIZE)
    rows = []
    for i in range(s, e):
        it = items[i]
        rows.append(
            [
                InlineKeyboardButton(
                    f"{safe_text(it.title, 40)} • ⏱ {fmt_dur(it.duration)}",
                    callback_data=f"gp|{job_id}|pick_item|{i}",
                )
            ]
        )
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"gp|{job_id}|page_item|{page-1}"))
    if page < pages - 1:
        nav.append(InlineKeyboardButton("بعدی ➡️", callback_data=f"gp|{job_id}|page_item|{page+1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton("لغو", callback_data=f"gp|{job_id}|cancel|0")])
    return InlineKeyboardMarkup(rows)

def kb_formats(job_id: str, fmt_count: int, page: int, send_mode: str, with_subs: bool, fmts: Optional[List[FormatChoice]] = None) -> InlineKeyboardMarkup:
    pages = max(1, math.ceil(fmt_count / PAGE_SIZE))
    s = page * PAGE_SIZE
    e = min(fmt_count, s + PAGE_SIZE)
    rows = []
    for i in range(s, e):
        if fmts and 0 <= i < len(fmts):
            f = fmts[i]
            fps = f"@{f.fps}" if f.fps else ""
            label = f"{f.resolution or '—'}{fps} • {f.ext or '?'} • {fmt_bytes(f.filesize)}"
        else:
            label = f"کیفیت #{i+1}"
        rows.append([InlineKeyboardButton(label, callback_data=f"gp|{job_id}|pick_fmt|{i}")])
    rows.append(
        [
            InlineKeyboardButton(("ارسال: فایل" if send_mode == "doc" else "ارسال: ویدئو/صوت"), callback_data=f"gp|{job_id}|toggle_send|0"),
            InlineKeyboardButton(("زیرنویس: روشن" if with_subs else "زیرنویس: خاموش"), callback_data=f"gp|{job_id}|toggle_subs|0"),
        ]
    )
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"gp|{job_id}|page_fmt|{page-1}"))
    if page < pages - 1:
        nav.append(InlineKeyboardButton("بعدی ➡️", callback_data=f"gp|{job_id}|page_fmt|{page+1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton("بازگشت", callback_data=f"gp|{job_id}|back_items|0")])
    rows.append([InlineKeyboardButton("لغو", callback_data=f"gp|{job_id}|cancel|0")])
    return InlineKeyboardMarkup(rows)

# ================= Handlers =================
@StreamBot.on_message(filters.private & filters.regex(URL_RE))
async def gp_handler(client: StreamBot, m: Message):
    lang = await get_i18n_texts(m.from_user.id)
    is_member, err, _ = await check_user_is_member(m.from_user.id)
    if not is_member:
        if err == "bot_not_admin":
            await m.reply(lang.get("FORCE_SUB_BOT_NOT_ADMIN"))
            return
        await m.reply(lang.get("FORCE_SUB_MESSAGE"))
        return
    if await is_user_banned(m.from_user.id):
        await m.reply_text(lang.get("BANNED_USER_ERROR"), quote=True)
        return
    if not await is_user_authorized(m.from_user.id):
        await m.reply_text(lang.get("NOT_AUTHORIZED"), quote=True)
        return

    url = URL_RE.findall(m.text or "")[0]
    wait = await m.reply_text("⏳ در حال اسکن صفحه برای یافتن ویدئوها...", quote=True)

    try:
        items = await asyncio.get_running_loop().run_in_executor(None, extract_items, url)
    except Exception as e:
        await safe_edit(wait, f"❌ خطا در استخراج: <code>{str(e)[:400]}</code>")
        return

    if not items:
        await safe_edit(wait, "❌ موردی یافت نشد.")
        return

    job_id = uuid.uuid4().hex[:10]
    JOBS[job_id] = {
        "user_id": m.from_user.id,
        "items": items,
        "items_page": 0,
        "formats": None,
        "formats_page": 0,
        "chosen_item_idx": None,
        "send_mode": "doc",
        "with_subs": False,
    }
    await safe_edit(wait, f"✅ {len(items)} مورد پیدا شد. یکی را انتخاب کن:")
    await m.reply_text("🎬 فهرست ویدئوها:", reply_markup=kb_items(job_id, items, 0), quote=True)

@StreamBot.on_callback_query(filters.regex(r"^gp\|"))
async def gp_cb(client: StreamBot, q: CallbackQuery):
    await q.answer()
    try:
        _, job_id, action, param = q.data.split("|", 3)
    except Exception:
        await q.answer("داده نامعتبر", show_alert=True)
        return

    job = JOBS.get(job_id)
    if not job:
        await q.answer("وظیفه پیدا نشد", show_alert=True)
        return

    if action == "cancel":
        JOBS.pop(job_id, None)
        try:
            await q.message.edit_text("❌ لغو شد")
        except errors.MessageNotModified:
            pass
        return

    if action == "page_item":
        job["items_page"] = max(0, int(param))
        try:
            await q.message.edit_reply_markup(kb_items(job_id, job["items"], job["items_page"]))
        except errors.MessageNotModified:
            pass
        return

    if action == "back_items":
        job["formats"] = None
        job["formats_page"] = 0
        try:
            await q.message.edit_text("🎬 فهرست ویدئوها:", reply_markup=kb_items(job_id, job["items"], job["items_page"]))
        except Exception:
            await q.message.edit_reply_markup(kb_items(job_id, job["items"], job["items_page"]))
        return

    if action == "pick_item":
        idx = int(param)
        items: List[VideoItem] = job["items"]
        if idx < 0 or idx >= len(items):
            await q.answer("مورد نامعتبر", show_alert=True)
            return
        chosen = items[idx]
        job["chosen_item_idx"] = idx
        status = await q.message.reply_text(
            f"⏳ استخراج کیفیت‌ها برای:\n<b>{safe_text(chosen.title, 200)}</b>", quote=True
        )

        def _run():
            return extract_formats(chosen.url)

        try:
            info, fmts = await asyncio.get_running_loop().run_in_executor(None, _run)
        except Exception as e:
            await safe_edit(status, f"❌ خطا در استخراج کیفیت‌ها: <code>{str(e)[:400]}</code>")
            return

        if not fmts:
            await safe_edit(status, "❌ کیفیتی پیدا نشد.")
            return

        # خلاصه کیفیت‌ها
        lines = []
        for i, f in enumerate(fmts[:30]):
            fps = f"@{f.fps}" if f.fps else ""
            lines.append(f"{i+1:02d}) {f.resolution or f.ext}{fps} • {f.ext} • {fmt_bytes(f.filesize)}")
        await safe_edit(status, "🔽 بخشی از کیفیت‌ها:\n" + "\n".join(lines))

        job["formats"] = fmts
        job["formats_page"] = 0
        await q.message.reply_text(
            "🎚 یکی از کیفیت‌ها را انتخاب کن:",
            reply_markup=kb_formats(job_id, len(fmts), 0, job["send_mode"], job["with_subs"], fmts=fmts),
            quote=True,
        )
        return

    if action == "page_fmt":
        job["formats_page"] = max(0, int(param))
        try:
            await q.message.edit_reply_markup(
                kb_formats(
                    job_id,
                    len(job["formats"] or []),
                    job["formats_page"],
                    job["send_mode"],
                    job["with_subs"],
                    fmts=job.get("formats"),
                )
            )
        except errors.MessageNotModified:
            pass
        return

    if action == "toggle_send":
        job["send_mode"] = "doc" if job["send_mode"] != "doc" else "stream"
        try:
            await q.message.edit_reply_markup(
                kb_formats(
                    job_id,
                    len(job["formats"] or []),
                    job["formats_page"],
                    job["send_mode"],
                    job["with_subs"],
                    fmts=job.get("formats"),
                )
            )
        except errors.MessageNotModified:
            pass
        return

    if action == "toggle_subs":
        job["with_subs"] = not job["with_subs"]
        try:
            await q.message.edit_reply_markup(
                kb_formats(
                    job_id,
                    len(job["formats"] or []),
                    job["formats_page"],
                    job["send_mode"],
                    job["with_subs"],
                    fmts=job.get("formats"),
                )
            )
        except errors.MessageNotModified:
            pass
        return

    if action == "pick_fmt":
        if job.get("formats") is None or job.get("chosen_item_idx") is None:
            await q.answer("ابتدا ویدئو را انتخاب کنید.", show_alert=True)
            return
        fi = int(param)
        fmts: List[FormatChoice] = job["formats"]
        if fi < 0 or fi >= len(fmts):
            await q.answer("کیفیت نامعتبر", show_alert=True)
            return
        fch = fmts[fi]
        vitem: VideoItem = job["items"][job["chosen_item_idx"]]
        status = await q.message.reply_text(
            f"⏳ دانلود: <b>{safe_text(vitem.title, 120)}</b>\n"
            f"فرمت: <code>{fch.resolution or fch.ext}</code> • {fmt_bytes(fch.filesize)}\n"
            f"{'📝 با زیرنویس' if job['with_subs'] else ''}",
            quote=True,
        )
        asyncio.create_task(_run_job(client, job, vitem, fch, status))
        return

# ================= Core job runner =================
async def _run_job(client: StreamBot, job: Dict[str, Any], vitem: VideoItem, fch: FormatChoice, status: Message):
    async with JOB_SEM:
        user_id = job["user_id"]
        send_mode = job.get("send_mode", "doc")
        as_doc = send_mode == "doc"
        with_subs = bool(job.get("with_subs"))

        tmpdir = tempfile.mkdtemp(prefix="gp_")
        try:
            # دانلود
            def _do():
                return download_with_ytdlp(vitem.url, fch, tmpdir, with_subs)

            try:
                dl_info = await asyncio.get_running_loop().run_in_executor(None, _do)
            except Exception as e:
                await safe_edit(status, f"❌ خطا در دانلود: <code>{str(e)[:400]}</code>")
                return

            fpath = determine_path(dl_info, tmpdir)
            if not fpath or not os.path.exists(fpath):
                await safe_edit(status, "❌ فایل خروجی پیدا نشد.")
                return

            # تضمین پسوند صحیح
            chosen_ext = (fch.ext or "").lower().strip(".")
            if not chosen_ext:
                chosen_ext = (dl_info.get("ext") or "").lower().strip(".")
            base_noext, current_ext = os.path.splitext(fpath)
            if not chosen_ext and current_ext:
                chosen_ext = current_ext.lower().strip(".")
            if chosen_ext:
                desired_path = base_noext + "." + chosen_ext
                if (not current_ext) or (current_ext.lower().strip(".") != chosen_ext):
                    try:
                        os.replace(fpath, desired_path)
                        fpath = desired_path
                    except Exception:
                        pass

            # نام محلی امن (فارسی/انگلیسی/اعداد مجاز، بدون underscore)
            base = os.path.basename(fpath)
            stem, ext = os.path.splitext(base)
            if not ext and chosen_ext:
                base = stem + "." + chosen_ext
            safe_local = clean_local_filename(base)
            final_path = fpath if base == safe_local else os.path.join(tmpdir, safe_local)
            if final_path != fpath:
                try:
                    os.replace(fpath, final_path)
                except Exception:
                    final_path = fpath  # اگر rename خطا داد

            # محدودیت ترافیک
            traffic = await get_user_traffic_details(user_id)
            limit_gb = traffic.get("traffic_limit_gb")
            size_mb = os.path.getsize(final_path) / (1024 * 1024)
            if limit_gb is not None and (traffic.get("total_size", 0.0) / 1024 + size_mb / 1024) > limit_gb:
                await safe_edit(status, "❌ سقف ترافیک شما به پایان رسیده است.")
                return

            await safe_edit(status, "⬆️ در حال آپلود…")
            await upload_and_link(client, user_id, final_path, status, as_doc)
            try:
                await update_stats(user_id, size_mb)
            except Exception:
                pass
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
