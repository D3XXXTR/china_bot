from aiogram import F, Router, Bot
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, Message,
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
)

from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
import html
from aiogram.fsm.state import State, StatesGroup


class AdminState(StatesGroup):
    waiting_amount = State()
    wait_reply = State()
    wait_delete_code = State()
    search_code = State()



admin_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📋 Все заказы"), KeyboardButton(text="🔍 Поиск по коду")],
        [KeyboardButton(text="🗂 Все чаты"), KeyboardButton(text="📨 Оплаченные товары")]
    ],
    resize_keyboard=True
)

def register_admin_handlers(dp, conn, cursor, ADMIN_IDS, bot):
    router = Router()

    @router.message(F.text == "📋 Все заказы")
    async def show_all_orders(message: Message):

        cursor.execute("SELECT code, link, details, quantity, status, created_at, amount FROM orders ORDER BY id ASC")
        rows = cursor.fetchall()
        if not rows:
            return await message.answer("Нет заказов.")

        for row in rows:
            code, link, details, quantity, status, created_at, amount = row
            safe_link = html.escape(link) if link and link.startswith("http") else ""
            product_link = f'<a href="{safe_link}">Товар</a>' if safe_link else "Товар"

            text = (
                f"# {code}\n🔗 {product_link}\n📌 {details}\n🔢 {quantity} шт\n"
                f"📦 {status}\n🕒 {created_at}\n💰 Сумма: {amount or '—'} ₽\n"
            )
            keyboard = [[InlineKeyboardButton(text="🗑 Удалить", callback_data=f"admin_delete_{code}")]]

            if status in ["🕐 В ожидании", "В ожидании"]:
                keyboard.insert(0, [InlineKeyboardButton(text="💰 Указать сумму", callback_data=f"setamount_{code}")])
            if amount and status not in ["✅ Отправлен", "Можно забирать"]:
                keyboard.insert(0, [InlineKeyboardButton(text="🚚 Отправлен", callback_data=f"mark_sent_{code}")])
            if status == "✅ Отправлен":
                keyboard.insert(0, [InlineKeyboardButton(text="📦 Можно забирать", callback_data=f"ready_{code}")])

            buttons = InlineKeyboardMarkup(inline_keyboard=keyboard)

            await message.answer(text, parse_mode="HTML", disable_web_page_preview=True, reply_markup=buttons)

    @router.callback_query(F.data.startswith("ready_"))
    async def mark_ready(callback: CallbackQuery):
        code = callback.data.replace("ready_", "")
        cursor.execute("UPDATE orders SET status = 'Можно забирать' WHERE code = ?", (code,))
        conn.commit()
        await callback.message.edit_reply_markup()
        await callback.answer("📦 Статус обновлён на 'Можно забирать'")
        cursor.execute("SELECT user_id FROM orders WHERE code = ?", (code,))
        user = cursor.fetchone()
        if user:
            await bot.send_message(user[0], f"📦 Ваш заказ #{code} можно забирать!")

    @router.callback_query(F.data.startswith("admin_delete_"))
    async def admin_delete_order(callback: CallbackQuery):
        code = callback.data.replace("admin_delete_", "")
        cursor.execute("DELETE FROM orders WHERE code = ?", (code,))
        conn.commit()
        await callback.message.edit_text(f"🗑 Заказ #{code} удалён.")
        await callback.answer("Удалено")

    @router.callback_query(F.data.startswith("setamount_"))
    async def ask_amount(callback: CallbackQuery, state: FSMContext):
        code = callback.data.replace("setamount_", "")
        await state.set_state(AdminState.waiting_amount)
        await state.update_data(code=code)
        await callback.message.answer(f"💰 Введите сумму для заказа #{code}:")

    @router.callback_query(F.data.startswith("mark_sent_"))
    async def mark_order_sent(callback: CallbackQuery):
        code = callback.data.replace("mark_sent_", "")
        cursor.execute("UPDATE orders SET status = '✅ Отправлен' WHERE code = ?", (code,))
        conn.commit()
        await callback.message.edit_reply_markup()
        await callback.answer("📦 Статус обновлён")
        await callback.message.answer(f"✅ Заказ #{code} отмечен как отправленный.")
        cursor.execute("SELECT user_id FROM orders WHERE code = ?", (code,))
        user = cursor.fetchone()
        if user:
            await bot.send_message(user[0], f"🚚 Ваш заказ #{code} был отправлен! Ожидайте доставку в Симферополь.")

    @router.message(F.text == "🔍 Поиск по коду")
    async def search_by_code_prompt(message: Message, state: FSMContext):
        await message.answer("Введите: [код заказа] ")
        await state.set_state(AdminState.search_code)

    @router.message(AdminState.search_code)
    async def search_by_code(message: Message, state: FSMContext):
        code = message.text.strip()
        cursor.execute("SELECT link, details, quantity, status, created_at, amount FROM orders WHERE code = ?", (code,))
        result = cursor.fetchone()
        if result:
            link, details, quantity, status, created_at, amount = result
            safe_link = html.escape(link) if link and link.startswith("http") else ""
            product_link = f'<a href="{safe_link}">Товар</a>' if safe_link else "Товар"
            await message.answer(
                f"# {code}\n"
                f"🔗 {product_link}\n"
                f"📌 {details}\n"
                f"🔢 {quantity} шт\n"
                f"📦 Статус: {status}\n"
                f"🕒 {created_at}\n"
                f"💰 Сумма: {amount or '—'} ₽",
                parse_mode="HTML",
                disable_web_page_preview=True
            )
        else:
            await message.answer("❗ Заказ не найден.")
        await state.clear()


    @router.message(AdminState.waiting_amount)
    async def set_amount(message: Message, state: FSMContext):
        try:
            amount = ''.join(c for c in message.text if c.isdigit() or c == '.').strip()
            data = await state.get_data()
            code = data.get("code")

            if not code:
                return await message.answer("❗ Ошибка: код заказа не найден в состоянии.")

            cursor.execute("UPDATE orders SET amount = ?, status = 'Ожидает оплаты' WHERE code = ?", (amount, code))
            conn.commit()

            cursor.execute("SELECT user_id FROM orders WHERE code = ?", (code,))
            user = cursor.fetchone()
            if user:
                user_id = user[0]
                await bot.send_message(
                    user_id,
                    f"📌 Заказ #{code} обновлён. Сумма к оплате: {amount} ₽.\nПерейдите в '📦 Мои заказы', чтобы оплатить."
                )

            await message.answer(f"✅ Сумма {amount} ₽ для заказа #{code} отправлена пользователю.")
        except Exception as e:
            print("Ошибка при установке суммы:", e)
            await message.answer("❗ Неверный формат. Просто введите сумму числом (например: 1490.50)")
        await state.clear()

    @router.message(F.text == "🗑 Удалить заказ")
    async def ask_delete(message: Message, state: FSMContext):
        await message.answer("Введите код заказа для удаления:")
        await state.set_state(AdminState.wait_delete_code)

    @router.message(AdminState.wait_delete_code)
    async def delete_order(message: Message, state: FSMContext):
        code = message.text.strip()
        cursor.execute("DELETE FROM orders WHERE code = ?", (code,))
        conn.commit()
        await message.answer(f"🗑 Заказ #{code} удалён.")
        await state.clear()

    @router.message(F.text == "📨 Оплаченные товары")
    async def show_uploaded_checks(message: Message):
        cursor.execute("SELECT code, user_id, check_file_id FROM orders WHERE check_file_id IS NOT NULL AND status = '🕓 Ожидает подтверждения' ORDER BY id DESC LIMIT 10")
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

    @router.message(F.text == "🗂 Все чаты")
    async def show_all_chats(message: Message):
        cursor.execute(
            "SELECT user_id, MAX(id) as last_id FROM support_messages GROUP BY user_id ORDER BY last_id DESC")
        users = cursor.fetchall()
        if not users:
            return await message.answer("Нет чатов с пользователями.")

        for user_id, _ in users:
            # Пытаемся получить последнее сообщение или заказ
            cursor.execute("SELECT details, code FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,))
            row = cursor.fetchone()
            summary = f"🧾 Последний заказ: #{row[1]} — {row[0]}" if row else ""

            # Получаем username и имя из метода get_chat
            try:
                user = await bot.get_chat(user_id)
                username = f"@{user.username}" if user.username else "—"
                full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
                user_link = f'<a href="tg://user?id={user.id}">{full_name or username}</a>'
            except Exception as e:
                print(f"Не удалось получить info о user_id={user_id}:", e)
                username = "—"
                full_name = "—"
                user_link = f"ID: {user_id}"

            buttons = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="💬 Ответить", callback_data=f"reply_{user_id}"),
                    InlineKeyboardButton(text="🗑 Удалить чат", callback_data=f"deletechat_{user_id}")
                ]
            ])

            text = (
                f"👤 Пользователь: {user_link}\n"
                f"🆔 ID: <code>{user_id}</code>\n"
                f"📦 Код последнего заказа: #{row[1]}" if row else ""
            )
            await message.answer(text, reply_markup=buttons, parse_mode="HTML")

    @router.callback_query(F.data.startswith("deletechat_"))
    async def delete_chat(callback: CallbackQuery):
        user_id = int(callback.data.replace("deletechat_", ""))
        cursor.execute("DELETE FROM support_messages WHERE user_id = ?", (user_id,))
        conn.commit()
        await callback.message.edit_text(f"🗑 Чат с пользователем  <code>{user_id}</code> удалён.", parse_mode="HTML")
        await callback.answer()

    @router.callback_query(F.data.startswith("reply_"))
    async def start_reply(callback: CallbackQuery, state: FSMContext):
        await state.clear()  # ← ВАЖНО: очистка предыдущего состояния
        user_id = int(callback.data.replace("reply_", ""))
        await state.set_state(AdminState.wait_reply)
        await state.update_data(reply_user_id=user_id)
        await callback.message.answer(f"✍️ Напишите ответ для пользователя ID {user_id}")
        await callback.answer()

    @router.message(AdminState.wait_reply)
    async def send_admin_reply(message: Message, state: FSMContext):
        data = await state.get_data()
        user_id = data.get("reply_user_id")
        if user_id:
            try:
                buttons = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✉️ Ответить", callback_data=f"user_reply_{message.from_user.id}")]
                ])
                await bot.send_message(user_id, f"📬 Ответ от поддержки:\n\n{message.text}", reply_markup=buttons)
                await message.answer("✅ Ответ отправлен пользователю.")
            except Exception as e:
                print(f"Ошибка при отправке сообщения пользователю {user_id}:", e)
                await message.answer("❗ Не удалось отправить сообщение. Возможно, пользователь заблокировал бота.")

        else:
            await message.answer("❗ Не удалось найти ID пользователя.")
        await state.clear()

    dp.include_router(router)