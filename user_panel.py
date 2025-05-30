from aiogram import F, Router, types, Bot
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
import random
from dotenv import load_dotenv
import os
load_dotenv()

user_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📦 Мои заказы"), KeyboardButton(text="🛍 Оформить заказ")],
        [KeyboardButton(text="📦 В наличии"), KeyboardButton(text="📞 Поддержка")],
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

class SupportForm(StatesGroup):
    waiting_message = State()

def generate_order_code():
    return f"{random.randint(1000, 9999)}"

def register_user_handlers(dp, conn, cursor, bot, ADMIN_IDS):
    router = Router()


    # Обработчики команд, заказов, оплаты, поддержки
    @router.message(F.text.in_(["📦 Мои заказы", "📞 Поддержка", "📦 В наличии", "🛍 Оформить заказ"]))
    async def handle_main_menu_buttons(message: Message, state: FSMContext):
        await state.clear()
        if message.text == "📞 Поддержка":
            await state.set_state(SupportForm.waiting_message)
            await message.answer("📩 Напишите Ваш вопрос. Мы ответим как можно скорее.", reply_markup=user_menu)
        elif message.text == "📦 Мои заказы":
            cursor.execute("SELECT code, link, details, quantity, status, created_at, amount FROM orders WHERE user_id = ?", (message.from_user.id,))
            rows = cursor.fetchall()
            if not rows:
                return await message.answer("У вас пока нет заказов.", reply_markup=user_menu)
            for i, row in enumerate(rows, 1):
                code, link, details, quantity, status, created_at, amount = row
                product_link = f'<a href="{link}">Товар {i}</a>' if link.startswith("http") else f"Товар {i}"



                if status == "Оплачен":
                    status_display = "💳 Оплачен"
                elif status == "В ожидании":
                    status_display = "🟠 В ожидании"
                elif status == "Отправлен":
                    status_display = "🚚 Отправлен"
                else:
                    status_display = status

                text = (
                    f"# {code}\n"
                    f"🔗 {product_link}\n"
                    f"📌 {details}\n"
                    f"🔢 {quantity} шт\n"
                    f"{status_display}\n"
                    f"💰 Сумма: {amount or '—'} ₽"
                )
                buttons = None
                if status == "Ожидает оплаты" and amount:
                    buttons = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="💳 Оплатить", callback_data=f"pay_{code}")]
                    ])
                elif status not in ["Оплачен", "Отправлен", "💳 Оплачен", "✅ Отправлен", "🕓 Ожидает подтверждения",
                                    "Ожидает оплаты"]:
                    buttons = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="✏️ Изменить", callback_data=f"edit_{code}"),
                         InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_{code}")]
                    ])

                await message.answer(text, reply_markup=buttons, parse_mode="HTML", disable_web_page_preview=True)
        elif message.text == "📦 В наличии":
            await message.answer(
                '<b>📦 Товары в наличии:</b>\n👉 <a href="https://t.me/kitaychik_shop">Перейти в канал</a>',
                parse_mode="HTML", reply_markup=user_menu)

        elif message.text == "🛍 Оформить заказ":
            await message.answer("🔗 Пришлите ссылку на товар c aliexpress.ru wildberries.ru ozon.ru или другого сайта:", reply_markup=user_menu)
            await state.set_state(OrderForm.link)

    @router.callback_query(F.data == "start_order")
    async def handle_start_order_callback(callback: types.CallbackQuery, state: FSMContext):
        await callback.message.delete()
        await callback.message.answer("🔗 Пришлите ссылку на товар с aliexpress.ru wildberries.ru ozon.ru или другого сайта:", reply_markup=user_menu)
        await state.set_state(OrderForm.link)

    @router.callback_query(F.data.startswith("pay_"))
    async def handle_inline_payment(callback: types.CallbackQuery, state: FSMContext):
        code = callback.data.replace("pay_", "")
        cursor.execute("SELECT amount FROM orders WHERE code = ? AND user_id = ?", (code, callback.from_user.id))
        result = cursor.fetchone()
        if not result:
            return await callback.message.answer("❗ Заказ не найден.")

        amount = result[0]
        if not amount:
            return await callback.message.answer("❗ Сумма ещё не указана. Подождите, пока администратор её добавит.")

        await callback.message.answer(
            f"💰 Сумма к оплате: <b>{amount} ₽</b>\n"
            "💳 Переведите на карту (ВТБ банк):\n"
            "<code>89780520940</code>\n"
            "УМЕРОВА Э.И.\n\n"
            "📸 После оплаты отправьте чек в ответ на это сообщение.",
            parse_mode="HTML"
        )
    @router.message(OrderForm.link)
    async def get_link(message: Message, state: FSMContext):
        await state.update_data(link=message.text)
        await state.set_state(OrderForm.details)
        await message.answer("📌 Укажите параметры если они есть(через пробел, цвет, размер и т.д.) иначе отправьте слово 'нет' "":", reply_markup=user_menu)

    @router.message(OrderForm.details)
    async def get_details(message: Message, state: FSMContext):
        await state.update_data(details=message.text)
        await state.set_state(OrderForm.quantity)
        await message.answer("🔢 Сколько штук:", reply_markup=user_menu)

    @router.message(OrderForm.quantity)
    async def get_quantity(message: Message, state: FSMContext):
        await state.update_data(quantity=message.text)
        data = await state.get_data()
        code = generate_order_code()
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        cursor.execute("INSERT INTO orders (code, link, details, quantity, user_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                       (code, data['link'], data['details'], data['quantity'], message.from_user.id, now))
        conn.commit()
        await message.answer(f"✅ Заказ оформлен! 🆔 Код заказа: <code>{code}</code> \nОжидайте! Мы посчитаем сумму и добавим в заказ. Спасибо!", parse_mode="HTML", reply_markup=user_menu)
        await state.clear()

    @router.message(PaymentForm.waiting_amount)
    async def receive_amount(message: Message, state: FSMContext):
        amount = message.text.strip()
        await state.clear()
        await message.answer(
            f"💰 Сумма к оплате: <b>{amount} ₽</b>\n"
            "💳 Переведите на карту (ВТБ банк):\n<code>89780520940</code>\nУМЕРОВА Э.И.\n\n"
            "📸 После оплаты отправьте чек в ответ на это сообщение.",
            parse_mode="HTML"
        )

    @router.message(F.photo | F.document)
    async def receive_payment_proof(message: Message):
        file_id = message.photo[-1].file_id if message.photo else message.document.file_id
        cursor.execute("SELECT id, code FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT 1",
                       (message.from_user.id,))
        order = cursor.fetchone()
        if not order:
            return await message.answer("❗ Не найден активный заказ. Оформите его сначала.")
        order_id, code = order
        cursor.execute("UPDATE orders SET check_file_id = ?, status = '🕓 Ожидает подтверждения' WHERE id = ?",(file_id, order_id))
        conn.commit()
        await message.answer("✅ Чек получен, ожидайте подтверждение.")
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id,f"📥 Новый чек на заказ #{code} от пользователя {message.from_user.id}. Ожидает подтверждения.")
            except Exception as e:
                print(f"❗ Ошибка при уведомлении администратора {admin_id}:", e)

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
        cursor.execute("SELECT details FROM orders WHERE code = ?", (code,))
        details_result = cursor.fetchone()
        existing_details = details_result[0] if details_result else ""

        await callback.message.answer(
            f"Введите новые параметры (например: Чёрный XL):\n\n"
            f"📝 Текущие: <code>{existing_details}</code>",
            parse_mode="HTML"
        )

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

    @router.message(SupportForm.waiting_message)
    async def handle_support_message(message: Message, state: FSMContext):
        await state.clear()
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        cursor.execute("INSERT INTO support_messages (user_id, sender, message, timestamp) VALUES (?, ?, ?, ?)",
                       (message.from_user.id, "user", message.text, now))
        conn.commit()
        text = (
            f"👤 Пользователь: @{message.from_user.username or '—'} (id: <code>{message.from_user.id}</code>)"
            f"💬 Сообщение:{message.text}")
        buttons = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💬 Ответить", callback_data=f"reply_{message.from_user.id}")]])
        for admin_id in ADMIN_IDS:
            await bot.send_message(admin_id, text, parse_mode="HTML", reply_markup=buttons)
        await message.answer("✅ Ваше сообщение отправлено. Ожидайте ответа.", reply_markup=user_menu)

    dp.include_router(router)
