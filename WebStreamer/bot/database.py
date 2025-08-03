# WebStreamer/bot/database.py
import logging
import aiosqlite
import datetime
import sqlite3
from WebStreamer.vars import Var
from WebStreamer.bot.i18n import user_lang_cache, lock

DB_PATH = 'database.sqlite3'
DETECT_TYPES = sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES

async def init_db():
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        await db.execute("PRAGMA journal_mode=WAL")

        # Users Table
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                first_name TEXT, last_name TEXT, username TEXT,
                total_files INTEGER DEFAULT 0, total_size REAL DEFAULT 0.0,
                traffic_limit_gb REAL,
                join_date TIMESTAMP,
                is_banned BOOLEAN DEFAULT 0,
                language TEXT DEFAULT 'fa'
            )
        ''')

        # Links Table (with new columns)
        cursor = await db.execute("PRAGMA table_info(links)")
        columns = {row[1] for row in await cursor.fetchall()}
        if 'views' not in columns:
            await db.execute("ALTER TABLE links ADD COLUMN views INTEGER DEFAULT 0")
        if 'creation_date' not in columns:
            await db.execute("ALTER TABLE links ADD COLUMN creation_date TIMESTAMP")
        if 'password' not in columns:
            await db.execute("ALTER TABLE links ADD COLUMN password TEXT")
        if 'expiry_date' not in columns:
            await db.execute("ALTER TABLE links ADD COLUMN expiry_date TIMESTAMP")
            
        await db.execute('''
            CREATE TABLE IF NOT EXISTS links (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                file_name TEXT, file_size_mb REAL,
                file_unique_id TEXT NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                views INTEGER DEFAULT 0,
                creation_date TIMESTAMP,
                password TEXT,
                expiry_date TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')

        # Settings & Login Attempts Tables
        await db.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS login_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP, ip_address TEXT,
                username_attempt TEXT, successful BOOLEAN
            )
        ''')
        await db.commit()
    logging.info("Database initialized/updated successfully.")
    await add_owner_as_user()

async def add_owner_as_user():
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        if (await (await db.execute("SELECT 1 FROM users WHERE id = ?", (Var.OWNER_ID,))).fetchone()) is None:
            await db.execute(
                "INSERT INTO users (id, join_date, traffic_limit_gb) VALUES (?, ?, ?)",
                (Var.OWNER_ID, datetime.datetime.now(), None)
            )
            await db.commit()

async def add_or_update_user(user_id: int, first_name: str, last_name: str, username: str):
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        await db.execute("UPDATE users SET first_name=?, last_name=?, username=? WHERE id=?", (first_name, last_name, username, user_id))
        await db.commit()

async def insert_link(user_id: int, link_id: int, file_name: str, file_size_mb: float, file_unique_id: str, password: str = None, expiry_date: datetime = None):
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        await db.execute(
            "INSERT INTO links (id, user_id, file_name, file_size_mb, file_unique_id, creation_date, password, expiry_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (link_id, user_id, file_name, file_size_mb, file_unique_id, datetime.datetime.now(), password, expiry_date)
        )
        await db.commit()

async def get_link_with_owner_info(link_id: int) -> dict:
    """Returns link details along with owner's ban status."""
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT l.id, l.is_active, l.password, l.expiry_date, u.is_banned
            FROM links l JOIN users u ON l.user_id = u.id
            WHERE l.id = ?
            """,
            (link_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

# ... (other functions remain mostly the same, only adding new ones)
async def set_user_lang(user_id: int, lang_code: str):
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        async with lock:
            await db.execute("UPDATE users SET language = ? WHERE id = ?", (lang_code, user_id))
            await db.commit()
            user_lang_cache[user_id] = lang_code
async def is_user_authorized(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        return (await (await db.execute("SELECT 1 FROM users WHERE id = ?", (user_id,))).fetchone()) is not None
async def get_user_traffic_details(user_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        db.row_factory = aiosqlite.Row
        return dict(await (await db.execute("SELECT total_size, traffic_limit_gb FROM users WHERE id = ?", (user_id,))).fetchone() or {})
async def is_user_banned(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        return (res := await (await db.execute("SELECT is_banned FROM users WHERE id = ?", (user_id,))).fetchone()) and res[0] == 1
async def ban_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db: await db.execute("UPDATE users SET is_banned = 1 WHERE id = ?", (user_id,)); await db.commit()
async def unban_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db: await db.execute("UPDATE users SET is_banned = 0 WHERE id = ?", (user_id,)); await db.commit()
async def is_link_active(link_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        return (res := await (await db.execute("SELECT is_active FROM links WHERE id = ?", (link_id,))).fetchone()) and res[0] == 1
async def count_user_links(user_id: int, query: str = None) -> int:
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        sql = "SELECT COUNT(id) FROM links WHERE user_id = ? AND is_active = 1"
        params = [user_id]
        if query:
            sql += " AND file_name LIKE ?"
            params.append(f"%{query}%")
        return (await (await db.execute(sql, params)).fetchone())[0] or 0
async def delete_link(link_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db: await db.execute("UPDATE links SET is_active = 0 WHERE id = ? AND user_id = ?", (link_id, user_id)); await db.commit()
async def get_stats(user_id: int) -> tuple:
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        return await (await db.execute("SELECT total_files, total_size FROM users WHERE id = ?", (user_id,))).fetchone() or (0, 0.0)
async def add_user_by_admin(user_id: int, limit_gb: float = None):
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        await db.execute("INSERT INTO users (id, join_date, traffic_limit_gb) VALUES (?, ?, ?) ON CONFLICT(id) DO UPDATE SET traffic_limit_gb=excluded.traffic_limit_gb", (user_id, datetime.datetime.now(), limit_gb)); await db.commit()
async def update_user_limit(user_id: int, limit_gb: float = None):
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db: await db.execute("UPDATE users SET traffic_limit_gb = ? WHERE id = ?", (limit_gb, user_id)); await db.commit()
async def get_all_user_ids():
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        return [row[0] for row in await (await db.execute("SELECT id FROM users WHERE is_banned = 0")).fetchall()]
async def get_daily_join_stats():
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        db.row_factory = aiosqlite.Row
        return [dict(row) for row in await (await db.execute("SELECT DATE(join_date) as date, COUNT(id) as count FROM users WHERE join_date >= DATE('now', '-7 days') GROUP BY DATE(join_date) ORDER BY date ASC")).fetchall()]

# --- New/Modified Functions for Added Features ---

async def update_stats(user_id: int, file_size_mb: float):
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db: await db.execute("UPDATE users SET total_files = total_files + 1, total_size = total_size + ? WHERE id = ?", (file_size_mb, user_id)); await db.commit()
async def get_user_links(user_id: int, offset: int, limit: int, query: str = None) -> list:
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        db.row_factory = aiosqlite.Row
        sql = "SELECT id, file_name, file_size_mb, views FROM links WHERE user_id = ? AND is_active = 1"
        params = [user_id]
        if query:
            sql += " AND file_name LIKE ?"
            params.append(f"%{query}%")
        sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        cursor = await db.execute(sql, params)
        return [dict(row) for row in await cursor.fetchall()]
async def increment_link_views(link_id: int):
    async with aiosqlite.connect(DB_PATH) as db: await db.execute("UPDATE links SET views = views + 1 WHERE id = ?", (link_id,)); await db.commit()

# --- Functions for Admin Panel ---
async def get_db_settings() -> dict:
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        db.row_factory = aiosqlite.Row
        return {row['key']: row['value'] for row in await (await db.execute("SELECT key, value FROM settings")).fetchall()}
async def update_db_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db: await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)); await db.commit()
async def log_login_attempt(ip: str, username: str, success: bool):
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        await db.execute("INSERT INTO login_attempts (timestamp, ip_address, username_attempt, successful) VALUES (?, ?, ?, ?)", (datetime.datetime.now(), ip, username, success)); await db.commit()
async def get_login_attempts(limit: int = 100):
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        db.row_factory = aiosqlite.Row
        return [dict(row) for row in await (await db.execute("SELECT * FROM login_attempts ORDER BY timestamp DESC LIMIT ?", (limit,))).fetchall()]
async def get_db_stats_for_panel():
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        total_users = (await (await db.execute("SELECT COUNT(id) FROM users")).fetchone())[0] or 0
        total_links = (await (await db.execute("SELECT COUNT(id) FROM links WHERE is_active = 1")).fetchone())[0] or 0
        total_traffic_mb = (await (await db.execute("SELECT SUM(total_size) FROM users")).fetchone())[0] or 0
        return {"total_users": total_users, "total_links": total_links, "total_traffic_gb": total_traffic_mb / 1024 if total_traffic_mb else 0}
async def get_daily_uploads_stats(days: int = 7):
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        db.row_factory = aiosqlite.Row
        return [dict(r) for r in await (await db.execute(f"SELECT DATE(creation_date) as date, COUNT(id) as count FROM links WHERE creation_date >= DATE('now', '-{days} days') GROUP BY date ORDER BY date ASC")).fetchall()]
async def get_top_traffic_users(limit: int = 5):
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        db.row_factory = aiosqlite.Row
        return [dict(r) for r in await (await db.execute("SELECT first_name, username, id, total_size FROM users WHERE total_size > 0 ORDER BY total_size DESC LIMIT ?", (limit,))).fetchall()]
async def get_file_type_stats():
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        db.row_factory = aiosqlite.Row
        query = """
            SELECT CASE
                WHEN file_name LIKE '%.mp4' OR file_name LIKE '%.mkv' THEN 'Video'
                WHEN file_name LIKE '%.mp3' OR file_name LIKE '%.flac' OR file_name LIKE '%.ogg' THEN 'Audio'
                WHEN file_name LIKE '%.zip' OR file_name LIKE '%.rar' OR file_name LIKE '%.7z' THEN 'Archive'
                WHEN file_name LIKE '%.pdf' OR file_name LIKE '%.docx' THEN 'Document'
                ELSE 'Other' END as file_type, COUNT(id) as count
            FROM links WHERE is_active = 1 GROUP BY file_type
        """
        return [dict(r) for r in await (await db.execute(query)).fetchall()]
async def search_all_links(file_q="", user_q="", status="active"):
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        db.row_factory = aiosqlite.Row
        sql = "SELECT l.*, u.id as user_id, u.first_name, u.username FROM links l JOIN users u ON l.user_id = u.id WHERE l.is_active = ? "
        params = [1 if status == "active" else 0]
        if file_q: sql += " AND l.file_name LIKE ?"; params.append(f"%{file_q}%")
        if user_q: sql += " AND (u.first_name LIKE ? OR u.username LIKE ? OR u.id LIKE ?)"; params.extend([f"%{user_q}%"]*3)
        sql += " ORDER BY l.creation_date DESC"
        return [dict(row) for row in await (await db.execute(sql, params)).fetchall()]
async def deactivate_links_by_ids(link_ids: list):
    async with aiosqlite.connect(DB_PATH) as db: await db.executemany("UPDATE links SET is_active = 0 WHERE id = ?", [(id,) for id in link_ids]); await db.commit()
async def deactivate_user_links(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db: await db.execute("UPDATE links SET is_active = 0 WHERE user_id = ?", (user_id,)); await db.commit()

async def get_all_users_for_panel(search_query: str = None):
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        db.row_factory = aiosqlite.Row
        sql, params = "SELECT * FROM users", []
        if search_query: sql += " WHERE first_name LIKE ? OR username LIKE ? OR id LIKE ?"; params.extend([f"%{search_query}%"]*3)
        sql += " ORDER BY join_date DESC"
        return [dict(row) for row in await (await db.execute(sql, params)).fetchall()]
async def get_user_details_for_panel(user_id: int):
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        db.row_factory = aiosqlite.Row
        user_data = await (await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))).fetchone()
        return dict(user_data) if user_data else None
async def get_all_links_for_user(user_id: int):
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        db.row_factory = aiosqlite.Row
        return [dict(r) for r in await (await db.execute("SELECT * FROM links WHERE user_id = ? AND is_active = 1 ORDER BY id DESC", (user_id,))).fetchall()]
async def admin_delete_link(link_id: int):
    async with aiosqlite.connect(DB_PATH) as db: await db.execute("UPDATE links SET is_active = 0 WHERE id = ?", (link_id,)); await db.commit()
async def get_link_by_id(link_id: int):
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, file_name, file_unique_id FROM links WHERE id = ? AND is_active = 1",
            (link_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None