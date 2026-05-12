import aiosqlite
import os
from dotenv import load_dotenv

load_dotenv()
DB = os.getenv("DATABASE_URL", "arcanum.db")

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    hwid TEXT,
    hwid_bind_date DATETIME,
    telegram_id INTEGER UNIQUE,
    telegram_username TEXT,
    role TEXT DEFAULT 'user'
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    plan TEXT NOT NULL,
    start_date DATETIME NOT NULL,
    end_date DATETIME,
    active INTEGER DEFAULT 1,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS verification_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    code TEXT NOT NULL,
    expires DATETIME NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS bot_states (
    telegram_id INTEGER PRIMARY KEY,
    state TEXT,
    data TEXT
);
"""

async def init_db():
    async with aiosqlite.connect(DB) as db:
        for stmt in CREATE_SQL.strip().split(";"):
            s = stmt.strip()
            if s:
                await db.execute(s)
        await db.commit()

async def fetchone(query, params=()):
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cur:
            return await cur.fetchone()

async def fetchall(query, params=()):
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cur:
            return await cur.fetchall()

async def execute(query, params=()):
    async with aiosqlite.connect(DB) as db:
        await db.execute(query, params)
        await db.commit()
