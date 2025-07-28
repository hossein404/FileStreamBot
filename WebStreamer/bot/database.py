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
    """Initialize SQLite database and create tables if they don't exist."""
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        # Check and add 'language' column if it doesn't exist for smooth updates
        try:
            cursor = await db.execute("PRAGMA table_info(users)")
            columns = [row[1] for row in await cursor.fetchall()]
            if 'language' not in columns:
                await db.execute("ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'fa'")
                logging.info("Added 'language' column to 'users' table.")
        except aiosqlite.OperationalError:
             # This means the 'users' table doesn't exist yet, which is fine.
             pass

        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                username TEXT,
                total_files INTEGER DEFAULT 0,
                total_size REAL DEFAULT 0.0,
                traffic_limit_gb REAL DEFAULT NULL,
                join_date timestamp,
                is_banned BOOLEAN NOT NULL CHECK (is_banned IN (0, 1)) DEFAULT 0,
                language TEXT DEFAULT 'fa'
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS links (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                file_name TEXT,
                file_size_mb REAL,
                file_unique_id TEXT NOT NULL,
                is_active BOOLEAN NOT NULL CHECK (is_active IN (0, 1)) DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        await db.commit()
    logging.info("Database initialized.")
    await add_owner_as_user()

async def add_owner_as_user():
    """Adds the OWNER_ID to the database with admin privileges if not already present."""
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        cursor = await db.execute("SELECT id FROM users WHERE id = ?", (Var.OWNER_ID,))
        if await cursor.fetchone() is None:
            logging.info(f"Adding Owner (ID: {Var.OWNER_ID}) to the database.")
            await db.execute(
                "INSERT INTO users (id, join_date, traffic_limit_gb) VALUES (?, ?, ?)",
                (Var.OWNER_ID, datetime.datetime.now(), None)
            )
            await db.commit()

async def add_or_update_user(user_id: int, first_name: str, last_name: str, username: str):
    """Updates an existing user's info. Does not add new users."""
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        await db.execute(
            "UPDATE users SET first_name = ?, last_name = ?, username = ? WHERE id = ?",
            (first_name, last_name, username, user_id)
        )
        await db.commit()

async def set_user_lang(user_id: int, lang_code: str):
    """Sets the language for a user."""
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        await db.execute("UPDATE users SET language = ? WHERE id = ?", (lang_code, user_id))
        await db.commit()
    # Update cache
    async with lock:
        user_lang_cache[user_id] = lang_code

async def insert_link(user_id: int, link_id: int, file_name: str, file_size_mb: float, file_unique_id: str):
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        await db.execute(
            "INSERT INTO links (id, user_id, file_name, file_size_mb, file_unique_id) VALUES (?, ?, ?, ?, ?)",
            (link_id, user_id, file_name, file_size_mb, file_unique_id)
        )
        await db.commit()

async def update_stats(user_id: int, file_size_mb: float):
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        await db.execute(
            "UPDATE users SET total_files = total_files + 1, total_size = total_size + ? WHERE id = ?",
            (file_size_mb, user_id)
        )
        await db.commit()

# --- User Authorization and Status ---

async def is_user_authorized(user_id: int) -> bool:
    """Check if a user exists in the database. Replaces ALLOWED_USERS."""
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        cursor = await db.execute("SELECT id FROM users WHERE id = ?", (user_id,))
        return await cursor.fetchone() is not None

async def get_user_traffic_details(user_id: int) -> dict:
    """Gets user's traffic usage and limit."""
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT total_size, traffic_limit_gb FROM users WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        return dict(row) if row else {}

async def is_user_banned(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        cursor = await db.execute("SELECT is_banned FROM users WHERE id = ?", (user_id,))
        result = await cursor.fetchone()
        return result[0] == 1 if result else False

async def ban_user(user_id: int):
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        await db.execute("UPDATE users SET is_banned = 1 WHERE id = ?", (user_id,))
        await db.commit()

async def unban_user(user_id: int):
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        await db.execute("UPDATE users SET is_banned = 0 WHERE id = ?", (user_id,))
        await db.commit()

# --- Link Management Functions ---

async def is_link_active(link_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        cursor = await db.execute("SELECT is_active FROM links WHERE id = ?", (link_id,))
        result = await cursor.fetchone()
        return result[0] == 1 if result else False

# --- Functions for regular user commands ---

async def get_user_links(user_id: int, offset: int, limit: int) -> list:
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, file_name, file_size_mb FROM links WHERE user_id = ? AND is_active = 1 ORDER BY id DESC LIMIT ? OFFSET ?",
            (user_id, limit, offset)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def count_user_links(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        cursor = await db.execute("SELECT COUNT(id) FROM links WHERE user_id = ? AND is_active = 1", (user_id,))
        result = await cursor.fetchone()
        return result[0] if result else 0

async def delete_link(link_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        await db.execute("UPDATE links SET is_active = 0 WHERE id = ? AND user_id = ?", (link_id, user_id))
        await db.commit()

async def get_stats(user_id: int) -> tuple:
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        cursor = await db.execute("SELECT total_files, total_size FROM users WHERE id = ?", (user_id,))
        result = await cursor.fetchone()
        return result if result else (0, 0.0)

# --- Functions for Admin Panel ---

async def add_user_by_admin(user_id: int, limit_gb: float = None):
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        await db.execute(
            "INSERT INTO users (id, join_date, traffic_limit_gb) VALUES (?, ?, ?) ON CONFLICT(id) DO UPDATE SET traffic_limit_gb=excluded.traffic_limit_gb",
            (user_id, datetime.datetime.now(), limit_gb)
        )
        await db.commit()

async def update_user_limit(user_id: int, limit_gb: float = None):
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        await db.execute("UPDATE users SET traffic_limit_gb = ? WHERE id = ?", (limit_gb, user_id))
        await db.commit()

async def admin_delete_link(link_id: int):
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        await db.execute("UPDATE links SET is_active = 0 WHERE id = ?", (link_id,))
        await db.commit()

async def get_db_stats_for_panel():
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        cursor = await db.execute("SELECT COUNT(id) FROM users")
        total_users = (await cursor.fetchone())[0] or 0
        cursor = await db.execute("SELECT COUNT(id) FROM links WHERE is_active = 1")
        total_links = (await cursor.fetchone())[0] or 0
        cursor = await db.execute("SELECT SUM(total_size) FROM users")
        total_traffic_mb = (await cursor.fetchone())[0] or 0
        total_traffic_gb = total_traffic_mb / 1024 if total_traffic_mb else 0
        return {
            "total_users": total_users,
            "total_links": total_links,
            "total_traffic_gb": total_traffic_gb
        }

async def get_all_users_for_panel(search_query: str = None):
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        db.row_factory = aiosqlite.Row
        sql = "SELECT * FROM users"
        params = []
        if search_query:
            sql += " WHERE first_name LIKE ? OR username LIKE ? OR id LIKE ?"
            params.extend([f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"])
        sql += " ORDER BY join_date DESC"
        cursor = await db.execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def get_user_details_for_panel(user_id: int):
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def get_all_links_for_user(user_id: int):
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM links WHERE user_id = ? AND is_active = 1 ORDER BY id DESC", (user_id,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def get_all_user_ids():
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        cursor = await db.execute("SELECT id FROM users WHERE is_banned = 0")
        rows = await cursor.fetchall()
        return [row[0] for row in rows]

async def get_daily_join_stats():
    async with aiosqlite.connect(DB_PATH, detect_types=DETECT_TYPES) as db:
        db.row_factory = aiosqlite.Row
        query = """
        SELECT DATE(join_date) as date, COUNT(id) as count
        FROM users
        WHERE join_date >= DATE('now', '-7 days')
        GROUP BY DATE(join_date)
        ORDER BY date ASC;
        """
        cursor = await db.execute(query)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]