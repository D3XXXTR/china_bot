import asyncio
import sqlite3

from aiogram import Bot, Dispatcher, F, types
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from admin_panel import admin_menu, register_admin_handlers
from user_panel import user_menu, register_user_handlers
from dotenv import load_dotenv
import os
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]


bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

conn = sqlite3.connect("orders.db")
cursor = conn.cursor()


cursor.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT,
    link TEXT,
    details TEXT,
    quantity TEXT,
    user_id INTEGER,
    status TEXT DEFAULT '🕐 В ожидании',
    created_at TEXT,
    amount TEXT,
    check_file_id TEXT
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS support_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    sender TEXT,
    message TEXT,
    timestamp TEXT
)
""")
conn.commit()

register_admin_handlers(dp, conn, cursor, ADMIN_IDS, bot)
register_user_handlers(dp, conn, cursor, bot, ADMIN_IDS)

@dp.message(F.text == "/start")
async def start(message: Message):
    if message.from_user.id in ADMIN_IDS:
        await message.answer("🔐 Админ-панель активна", reply_markup=admin_menu)
    else:
        text = (
            "👋 <b>Добро пожаловать в наш Telegram-бот для заказов из Китая!</b>\n\n"
            "С помощью этого бота вы можете легко и удобно:\n\n"
            "📦 <b>Оформить заказ</b>\n"
            "📋 <b>Следить за статусом заказа</b>\n"
            "💳 <b>Получить сумму к оплате</b>\n"
            "📢 У нас есть и товары в наличии! Посмотри в канале: @kitaychik_shop"
        )
        buttons = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛍 Оформить заказ", callback_data="start_order")],
            [InlineKeyboardButton(text="📦 Товары в наличии", url="https://t.me/kitaychik_shop")]
        ])
        await message.answer(text, reply_markup=buttons, parse_mode="HTML")

async def main():
    try:
        await dp.start_polling(bot)
    finally:
        conn.close()

if __name__ == "__main__":
    asyncio.run(main())
