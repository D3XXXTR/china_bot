from aiogram import F, Router, Bot
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, Message,
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

admin_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📋 Все заказы"), KeyboardButton(text="🗑 Удалить заказ")],
        [KeyboardButton(text="🔍 Поиск по коду"), KeyboardButton(text="🔁 Изменить статус")],
        [KeyboardButton(text="✅ Отправленные"), KeyboardButton(text="🕐 В ожидании")],
        [KeyboardButton(text="💰 Указать сумму"), KeyboardButton(text="📨 Оплаченные товары")]
    ],
    resize_keyboard=True
)

class SearchActions(StatesGroup):
    wait_code = State()

class AdminActions(StatesGroup):
    wait_delete_code = State()
    wait_edit_status = State()
    wait_amount = State()

def register_admin_handlers(dp, conn, cursor, admin_id, bot):
    router = Router()

    @router.message(F.text == "📋 Все заказы")
    async def show_all_orders(message: Message):
        cursor.execute("SELECT code, link, details, quantity, status, created_at, amount FROM orders ORDER BY id DESC LIMIT 10")
        rows = cursor.fetchall()
        if not rows:
            return await message.answer("Нет заказов.")
        text = "📋 Последние заказы:\n\n"
        for row in rows:
            text += (
                f"# {row[0]}\n🔗 {row[1]}\n📌 {row[2]}\n🔢 {row[3]} шт\n"
                f"📦 {row[4]}\n🕒 {row[5]}\n💰 Сумма: {row[6] or '—'} ₽\n\n"
            )
        await message.answer(text)

    @router.message(F.text == "🔍 Поиск по коду")
    async def search_by_code_prompt(message: Message, state: FSMContext):
        await message.answer("Введите: [код заказа] ")
        await state.set_state(SearchActions.wait_code)

    @router.message(SearchActions.wait_code)
    async def search_by_code(message: Message, state: FSMContext):
        code = message.text.strip()
        cursor.execute("SELECT link, details, quantity, status FROM orders WHERE code = ?", (code,))
        result = cursor.fetchone()
        if result:
            await message.answer(
                f"# {code}\n🔗 {result[0]}\n📌 {result[1]}\n🔢 {result[2]} шт\n📦 Статус: {result[3]}"
            )
        else:
            await message.answer("❗ Заказ не найден.")
        await state.clear()

    @router.message(F.text == "✅ Отправленные")
    async def show_sent_orders(message: Message):
        cursor.execute("SELECT code, link, details, quantity, status FROM orders WHERE status = '✅ Отправлен'")
        rows = cursor.fetchall()
        if not rows:
            return await message.answer("Нет отправленных заказов.")
        text = "✅ Отправленные заказы:\n\n"
        for row in rows:
            text += (
                f"# {row[0]}\n🔗 {row[1]}\n📌 {row[2]}\n🔢 {row[3]} шт\n📦 {row[4]}\n\n"
            )
        await message.answer(text)

    @router.message(F.text == "🕐 В ожидании")
    async def show_pending_orders(message: Message):
        cursor.execute("SELECT code, link, details, quantity, status FROM orders WHERE status = '🕐 В ожидании'")
        rows = cursor.fetchall()
        if not rows:
            return await message.answer("Нет заказов в ожидании.")
        text = "🕐 Заказы в ожидании:\n\n"
        for row in rows:
            text += (
                f"# {row[0]}\n🔗 {row[1]}\n📌 {row[2]}\n🔢 {row[3]} шт\n📦 {row[4]}\n\n"
            )
        await message.answer(text)

    @router.message(F.text == "💰 Указать сумму")
    async def ask_amount(message: Message, state: FSMContext):
        await message.answer("Введите код и сумму (например: 1234 1490.50):")
        await state.set_state(AdminActions.wait_amount)

    @router.message(AdminActions.wait_amount)
    async def set_amount(message: Message, state: FSMContext):
        try:
            code, amount = message.text.strip().split(" ", 1)
            cursor.execute("UPDATE orders SET amount = ? WHERE code = ?", (amount, code))
            conn.commit()
            cursor.execute("SELECT user_id FROM orders WHERE code = ?", (code,))
            user = cursor.fetchone()
            if user:
                user_id = user[0]
                await bot.send_message(user_id,
                   f"💰 Сумма к оплате (за все заказы): <b>{amount} ₽</b>\n"
                   "💳 Переведите на карту (ВТБ банк):\n<code>89780520940</code>\nУМЕРОВА Э.И.\n\n"
                   "📸 После оплаты отправьте чек в ответ на это сообщение.",
                    parse_mode="HTML"
                )
            await message.answer(f"✅ Сумма {amount} ₽ для заказа #{code} отправлена пользователю.")
        except:
            await message.answer("❗ Неверный формат. Введите: код сумма (например: 1234 1490.50)")
        await state.clear()

    @router.message(F.text == "🔁 Изменить статус")
    async def ask_status_update(message: Message, state: FSMContext):
        await message.answer("Введите код и новый статус (пример: 1234 ✅ Отправлен):")
        await state.set_state(AdminActions.wait_edit_status)

    @router.message(AdminActions.wait_edit_status)
    async def update_status(message: Message, state: FSMContext):
        try:
            code, status = message.text.strip().split(" ", 1)
            cursor.execute("UPDATE orders SET status = ? WHERE code = ?", (status, code))
            conn.commit()
            cursor.execute("SELECT user_id FROM orders WHERE code = ?", (code,))
            user = cursor.fetchone()
            if user:
                await bot.send_message(user[0], f"🔔 Статус заказа #{code} обновлён: {status}")
            await message.answer(f"✅ Статус заказа #{code} обновлён.")
        except:
            await message.answer("❗ Формат: 1234 ✅ Отправлен")
        await state.clear()

    @router.message(F.text == "🗑 Удалить заказ")
    async def ask_delete(message: Message, state: FSMContext):
        await message.answer("Введите код заказа для удаления:")
        await state.set_state(AdminActions.wait_delete_code)

    @router.message(AdminActions.wait_delete_code)
    async def delete_order(message: Message, state: FSMContext):
        code = message.text.strip()
        cursor.execute("DELETE FROM orders WHERE code = ?", (code,))
        conn.commit()
        await message.answer(f"🗑 Заказ #{code} удалён.")
        await state.clear()

    @router.message(F.text == "📨 Оплаченные товары")
    async def show_uploaded_checks(message: Message):
        cursor.execute("SELECT code, user_id, check_file_id FROM orders WHERE check_file_id IS NOT NULL ORDER BY id DESC LIMIT 10")
        rows = cursor.fetchall()
        if not rows:
            return await message.answer("Нет загруженных чеков.")
        for code, user_id, file_id in rows:
            caption = f"📥 Чек на заказ #{code}\n👤 User ID: {user_id}"
            buttons = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data=f"confirm_{code}")]
            ])
            if file_id.startswith("AgAC"):
                await bot.send_photo(message.chat.id, photo=file_id, caption=caption, reply_markup=buttons)
            else:
                await bot.send_document(message.chat.id, document=file_id, caption=caption, reply_markup=buttons)

    @router.callback_query(F.data.startswith("confirm_"))
    async def confirm_payment(callback: CallbackQuery):
        code = callback.data.replace("confirm_", "")
        cursor.execute("UPDATE orders SET status = '💳 Оплачен' WHERE code = ?", (code,))
        conn.commit()
        await callback.message.edit_reply_markup()
        await callback.message.answer(f"✅ Заказ #{code} помечен как оплаченный.")
        cursor.execute("SELECT user_id FROM orders WHERE code = ?", (code,))
        user = cursor.fetchone()
        if user:
            await bot.send_message(user[0], f"✅ Ваш заказ #{code} подтверждён и оплачен.")

    dp.include_router(router)


