import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from admin_panel import admin_menu, register_admin_handlers
from user_panel import user_menu, register_user_handlers

BOT_TOKEN = "6797221233:AAEOsDapzac2TR50AhJ8Dx1fkXMvn2deX7w"
ADMIN_ID = 86161915 # 861619156


bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

conn = sqlite3.connect("orders.db")
cursor = conn.cursor()
cursor.execute(
    "CREATE TABLE IF NOT EXISTS orders ("
    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
    "code TEXT, "
    "link TEXT, "
    "details TEXT, "
    "quantity TEXT, "
    "user_id INTEGER, "
    "status TEXT DEFAULT '🕐 В ожидании', "
    "created_at TEXT, "
    "amount TEXT, "
    "check_file_id TEXT"
    ")"
)
conn.commit()

register_admin_handlers(dp, conn, cursor, ADMIN_ID, bot)
register_user_handlers(dp, conn, cursor, bot)

@dp.message(F.text == "/start")
async def start(message: Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("🔐 Админ-панель активна", reply_markup=admin_menu)
    else:
        text = (
            "👋 <b>Добро пожаловать в наш Telegram-бот для заказов из Китая!</b>\n\n"
            "С помощью этого бота вы можете легко и удобно:\n\n"
            "📦 <b>Оформить заказ</b> на товар с Aliexpress или другого китайского сайта\n"
            "📋 <b>Следить за статусом</b> своих заказов в реальном времени\n"
            "💳 <b>Получить сумму к оплате</b> и отправить чек прямо в чат\n"
            "📞 <b>Обратиться в поддержку</b> в один клик\n\n"
            "Всё управление — в пару нажатий. Просто попробуйте оформить заказ 👇"
        )

        buttons = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛍 Оформить заказ", callback_data="start_order")]
        ])
        await message.answer(text, reply_markup=buttons, parse_mode="HTML")





async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())