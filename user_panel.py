from aiogram import F, Router, types, Bot
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
import random

user_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📦 Мои заказы"), KeyboardButton(text="🛍 Оформить заказ")],
        [KeyboardButton(text="💳 Оплата"), KeyboardButton(text="📞 Поддержка")],
    ],
    resize_keyboard=True
)

class OrderForm(StatesGroup):
    link = State()
    details = State()
    quantity = State()

class EditForm(StatesGroup):
    wait_code = State()
    wait_new_details = State()

class PaymentForm(StatesGroup):
    waiting_amount = State()

def generate_order_code():
    return f"{random.randint(1000, 9999)}"

def register_user_handlers(dp, conn, cursor, bot):
    router = Router()
    ADMIN_ID = 1174813870

    @router.message(F.text == "🛍 Оформить заказ")
    async def start_order(message: Message, state: FSMContext):
        await message.answer("🔗 Пришлите ссылку на товар c aliexpress.ru:", reply_markup=user_menu)
        await state.set_state(OrderForm.link)

    @router.callback_query(F.data == "start_order")
    async def handle_start_order_callback(callback: types.CallbackQuery, state: FSMContext):
        await callback.message.delete()
        await start_order(callback.message, state)  # повторно вызываем функцию оформления

    @router.message(OrderForm.link)
    async def get_link(message: Message, state: FSMContext):
        await state.update_data(link=message.text)
        await state.set_state(OrderForm.details)
        await message.answer("📌 Укажите параметры (через пробел, цвет, размер и т.д.):")

    @router.message(OrderForm.details)
    async def get_details(message: Message, state: FSMContext):
        await state.update_data(details=message.text)
        await state.set_state(OrderForm.quantity)
        await message.answer("🔢 Сколько штук:")

    @router.message(OrderForm.quantity)
    async def get_quantity(message: Message, state: FSMContext):
        await state.update_data(quantity=message.text)
        data = await state.get_data()
        code = generate_order_code()
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        cursor.execute("INSERT INTO orders (code, link, details, quantity, user_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                       (code, data['link'], data['details'], data['quantity'], message.from_user.id, now))
        conn.commit()
        await message.answer(f"✅ Заказ оформлен и находится в обработке!\n💰Стоимость заказа будет направлена позже. Ожидайте... \n🆔 Код заказа: <code>{code}</code>", parse_mode="HTML", reply_markup=user_menu)
        await state.clear()

    @router.message(F.text.in_(["📦 Мои заказы", "📞 Поддержка"]))
    async def handle_common_buttons(message: Message, state: FSMContext):
        await state.clear()
        if message.text == "📞 Поддержка":
            await message.answer("📞 Напишите в поддержку: @dekkstr")
        elif message.text == "📦 Мои заказы":
            cursor.execute("SELECT code, link, details, quantity, status, created_at, amount FROM orders WHERE user_id = ?", (message.from_user.id,))
            rows = cursor.fetchall()
            if not rows:
                return await message.answer("У вас пока нет заказов.")
            for i, row in enumerate(rows, 1):
                code, link, details, quantity, status, created_at, amount = row
                product_link = f'<a href="{link}">Товар {i}</a>' if link.startswith("http") else f"Товар {i}"

                text = (
                    f"# {code}\n"
                    f"🔗 {product_link}\n"
                    f"📌 {details}\n"
                    f"🔢 {quantity} шт\n"
                    f"📦 Статус: {status}\n"
                    f"💰 Сумма: {amount or '—'} ₽"
                )
                buttons = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✏️ Изменить", callback_data=f"edit_{code}"),
                     InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_{code}")]
                ])
                await message.answer(text, reply_markup=buttons, parse_mode="HTML", disable_web_page_preview=True)

    @router.message(F.text == "💳 Оплата")
    async def ask_payment_amount(message: Message, state: FSMContext):
        await state.set_state(PaymentForm.waiting_amount)
        await message.answer("Введите сумму к оплате (например: 1234.56):")

    @router.message(PaymentForm.waiting_amount)
    async def receive_amount(message: Message, state: FSMContext):
        amount = message.text.strip()
        await state.clear()
        await message.answer(
            f"💰 Сумма к оплате (за все заказы): <b>{amount} ₽</b>\n"
            "💳 Переведите на карту (ВТБ банк):\n<code>89780520940</code>\nУМЕРОВА Э.И.\n\n"
            "📸 После оплаты отправьте чек в ответ на это сообщение.",
            parse_mode="HTML"
        )

    @router.message(F.photo | F.document)
    async def receive_payment_proof(message: Message):
        file_id = message.photo[-1].file_id if message.photo else message.document.file_id
        cursor.execute("SELECT id FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT 1", (message.from_user.id,))
        order = cursor.fetchone()
        if order:
            order_id = order[0]
            cursor.execute("UPDATE orders SET check_file_id = ? WHERE id = ?", (file_id, order_id))
            conn.commit()
        await message.answer("✅ Чек получен, ожидайте подтверждение.")

    @router.callback_query(F.data.startswith("edit_"))
    async def edit_order_callback(callback: types.CallbackQuery, state: FSMContext):
        code = callback.data.replace("edit_", "")
        cursor.execute("SELECT status FROM orders WHERE code = ? AND user_id = ?", (code, callback.from_user.id))
        result = cursor.fetchone()
        if not result:
            return await callback.message.answer("❗ Заказ не найден.")
        if result[0] == "✅ Отправлен":
            return await callback.message.answer("❗ Этот заказ уже отправлен и не может быть изменён.")
        await state.update_data(code=code)
        await state.set_state(EditForm.wait_new_details)
        await callback.message.answer("Введите новые параметры (например: Цвет: чёрный, Размер: XL):")

    @router.message(EditForm.wait_new_details)
    async def update_details(message: Message, state: FSMContext):
        new_text = message.text.strip()
        data = await state.get_data()
        code = data["code"]
        cursor.execute("UPDATE orders SET details = ? WHERE code = ?", (new_text, code))
        conn.commit()
        await message.answer(f"✅ Заказ #{code} обновлён.")
        await state.clear()

    @router.callback_query(F.data.startswith("delete_"))
    async def delete_order_callback(callback: types.CallbackQuery):
        code = callback.data.replace("delete_", "")
        cursor.execute("SELECT id FROM orders WHERE code = ? AND user_id = ?", (code, callback.from_user.id))
        if not cursor.fetchone():
            return await callback.message.answer("❗ Заказ не найден.")
        cursor.execute("DELETE FROM orders WHERE code = ? AND user_id = ?", (code, callback.from_user.id))
        conn.commit()
        await callback.message.answer(f"🗑 Заказ #{code} удалён.")

    dp.include_router(router)