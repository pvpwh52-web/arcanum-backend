import asyncio, os, random, string, json
from datetime import datetime, timedelta
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from database import init_db, fetchone, fetchall, execute
from auth import hash_password

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
SITE_URL = os.getenv("SITE_URL", "https://arcanumclient.base44.app")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# FSM States
class BindStates(StatesGroup):
    waiting_login = State()

class RecoverStates(StatesGroup):
    waiting_login = State()

class AdminGiveSubStates(StatesGroup):
    waiting_login = State()
    confirm = State()

class AdminRoleStates(StatesGroup):
    waiting_login = State()

# Клавиатуры
USER_KB = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="🔗 Привязать аккаунт"), KeyboardButton(text="🔑 Восстановить пароль")]
], resize_keyboard=True)

ADMIN_KB = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="➕ Выдать подписку"), KeyboardButton(text="📋 Юзеры")],
    [KeyboardButton(text="⚙️ Сменить роль")]
], resize_keyboard=True)

def plan_inline_kb(username: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="7 дн", callback_data=f"plan:7d:{username}"),
         InlineKeyboardButton(text="30 дн", callback_data=f"plan:30d:{username}")],
        [InlineKeyboardButton(text="365 дн", callback_data=f"plan:365d:{username}"),
         InlineKeyboardButton(text="Навсегда", callback_data=f"plan:forever:{username}")],
    ])

def confirm_inline_kb(username: str, plan: str):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Выдать", callback_data=f"confirm_sub:{username}:{plan}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"),
    ]])

def users_inline_kb(users, page=0):
    per_page = 5
    start = page * per_page
    chunk = users[start:start + per_page]
    rows = []
    for u in chunk:
        rows.append([InlineKeyboardButton(text=f"👤 {u['username']} | {u['role']}", callback_data=f"user_info:{u['id']}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"users_page:{page-1}"))
    if start + per_page < len(users):
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"users_page:{page+1}"))
    if nav:
        rows.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=rows)

def user_detail_kb(user_id: int, role: str, has_sub: bool):
    rows = []
    if has_sub:
        rows.append([InlineKeyboardButton(text="❌ Деактивировать подписку", callback_data=f"deactivate_sub:{user_id}")])
    if role == "admin":
        rows.append([InlineKeyboardButton(text="👤 Сделать юзером", callback_data=f"set_role:{user_id}:user")])
    else:
        rows.append([InlineKeyboardButton(text="👑 Сделать админом", callback_data=f"set_role:{user_id}:admin")])
    rows.append([InlineKeyboardButton(text="◀️ Назад к списку", callback_data="users_page:0")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

async def main():
    await init_db()
    print("✅ Бот запущен (long polling)")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
