import logging
import time
import asyncio
from aiogram.enums import ChatType
from aiogram import F, Bot, types, Dispatcher
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from keyboards import materials_keyboard, main_keyboard, get_self_years_keyboard, get_year_buttons
from database import get_user_access, set_user_access, check_duplicate_file
from config import ADMIN_ID, GROUP_IDS

logger = logging.getLogger(__name__)

@F.callback_query.data.startswith("year_")
async def handle_year_selection(call: types.CallbackQuery):
    year = call.data.split("_")[1]

    text = """
🔹 Уровень САМОСТОЯТЕЛЬНЫЙ — чтобы увидеть свою будущую пенсию без сложных расчётов

📌 Подходит, если:
– не дружите с формулами, Excel, не понимаете алгоритм расчета на уровне госорганов
– просто хотите понять, почему у вас будет такая пенсия
– хотите узнать, что влияет на размер пенсии и можно ли что-то улучшить

📚 Вы получите:
✔️ Готовые материалы в понятной форме — таблицы и видео
✔️ Объяснение на примерах, без сложностей
✔️ Инструкции: что проверить, где взять данные, как не упустить важное
✔️ Конечный продукт с расчетом вашей пенсии

⏰ Доступ: 7 дней
💬 Вопросы — в общем чате можно задавать вопросы по заполнению таблицы
💳 Стоимость: 10 000 ₸

👇 Нажмите «✅ Оплатить», чтобы перейти к реквизитам.
"""
    await call.message.answer(text, reply_markup=get_year_buttons(year))

@F.callback_query.data.startswith("send_screenshot_")
async def handle_screenshot(call: types.CallbackQuery):
    user_id = call.from_user.id
    expire_time, current_tariff = await get_user_access(user_id)

    if expire_time and expire_time > time.time():
        await call.answer("❗ У вас уже есть активный доступ!", show_alert=True)
        return

    year_or_tariff = call.data.split("_")[2] if len(call.data.split("_")) > 2 else call.data.split("_")[1]
    await set_user_access(user_id, None, year_or_tariff)
    await call.message.answer(
        f"📄 Пожалуйста, отправьте PDF-файл фискального чека из Kaspi!\n\n"
        "📌 Как получить чек:\n"
        "1. После оплаты в Kaspi нажмите «Показать чек об оплате»\n"
        "2. Нажмите «Поделиться»\n"
        "3. Отправьте чек в этот чат\n\n"
    )

@F.callback_query.data.in_([
    "self", "basic", "pro", "offer",
    "send_screenshot_basic", "send_screenshot_pro",
    "get_materials", "used_link"
])
async def handle_callback(call: types.CallbackQuery, bot: Bot):
    if call.message.chat.type != ChatType.PRIVATE:
        return

    data = call.data
    user_id = call.from_user.id

    if data == "self":
        await call.message.answer("📅 Выберите год вашего выхода на пенсию:", reply_markup=get_self_years_keyboard())
        return

    if data == "basic":
        await set_user_access(user_id, None, "basic")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Оплатить", url="https://pay.kaspi.kz/pay/vx2s6z0c")],
            [InlineKeyboardButton(text="📄 Отправить чек", callback_data="send_screenshot_basic")]
        ])
        await call.message.answer(
        """
🔸 Уровень БАЗОВЫЙ — мини-курс для тех, кто хочет понимать расчёт пенсии и помогать другим

📚 Вы получите:
✔️ Готовый алгоритм расчёта пенсии — пошагово, без сложных формул
✔️ Примеры и шаблоны — как считать, где брать данные
✔️ Видео + текстовые материалы — всё по делу
✔️ Ответы на вопросы по расчёту (если что-то непонятно — разберём)

🧠 Подходит тем, кто:
– хочет разбираться в теме для себя и близких
– планирует помогать другим (как консультант или помощник)
– не хочет тратить время на самостоятельное изучение всех нюансов

⏰ Доступ: 30 дней
💬 Поддержка: вопрос-ответ в общем чате
💳 Стоимость: 50 000 ₸

👇 Нажмите «✅ Оплатить», чтобы перейти к реквизитам.
        """,
        reply_markup=keyboard)

    elif data == "pro":
        await set_user_access(user_id, None, "pro")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Оплатить", url="https://pay.kaspi.kz/pay/vx2s6z0c")],
            [InlineKeyboardButton(text="📄 Отправить чек", callback_data="send_screenshot_pro")]
        ])
        await call.message.answer("❌ Временно недоступно", reply_markup=keyboard)

    elif data == "get_materials":
        await call.answer()
        await call.message.edit_reply_markup(
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(
                        text="✅ Материалы получены",
                        callback_data="used_link"
                    )]
                ]
            )
        )
        expire_time, tariff = await get_user_access(user_id)
        if not expire_time or expire_time < time.time():
            return await call.message.answer("❌ У вас нет активного доступа.")

        tariff_chat_map = {
            "basic": -1002583988789,
            "2025": -1002529607781,
            "2026": -1002611068580,
            "2027": -1002607289832,
            "2028": -1002560662894,
            "2029": -1002645685285,
            "2030": -1002529375771,
            "2031": -1002262602915
        }

        chat_id = tariff_chat_map.get(tariff)
        if not chat_id:
            return await call.message.answer("❌ Не удалось определить канал по вашему тарифу.")

        try:
            invite = await bot.create_chat_invite_link(
                chat_id=chat_id,
                member_limit=1,
                expire_date=int(time.time()) + 15,
                creates_join_request=False
            )

            msg = await call.message.answer(
                f"🔐 Ваша персональная ссылка (исчезнет спустя 15 секунд):\n{invite.invite_link}"
            )

            await asyncio.sleep(15)
            try:
                await msg.delete()
            except Exception as e:
                logger.error(f"Не удалось удалить сообщение: {e}")

        except Exception as e:
            logger.error(f"Ошибка создания ссылки для чата {chat_id}: {e}")
            await call.message.answer("⚠️ Ошибка при создании ссылки.")

@F.callback_query.data == "used_link"
async def handle_used_link(call: types.CallbackQuery):
    await call.answer("Вы уже использовали эту ссылку", show_alert=True)

@F.callback_query.data.startswith("approve_")
async def approve_user(call: types.CallbackQuery, bot: Bot):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Недостаточно прав")

    user_id = int(call.data.split("_")[1])
    _, tariff = await get_user_access(user_id)

    if not tariff:
        return await call.answer("❌ У пользователя не выбран тариф. Сначала выберите тариф!")

    if tariff == "basic":
        duration = 30 * 86400
    elif tariff == "pro":
        duration = 60 * 86400
    elif tariff in [str(y) for y in range(2025, 2032)]:
        duration = 7 * 86400
    else:
        return await call.answer("❌ Неизвестный тариф.")

    expire_time = time.time() + duration
    await set_user_access(user_id, expire_time, tariff)

    with open("access_log.txt", "a", encoding="utf-8") as f:
        f.write(f"{user_id} | {tariff} | {time.ctime()} | {duration // 86400} дней\n")

    await bot.send_message(user_id, f"✅ Доступ уровня {tariff.upper()} выдан на {duration // 86400} дней!", reply_markup=materials_keyboard)

    await call.message.edit_reply_markup(reply_markup=None)
    await call.answer("Доступ выдан.")

def register_callback_handlers(dp: Dispatcher):
    dp.callback_query.register(handle_year_selection, lambda c: c.data.startswith("year_"))
    dp.callback_query.register(handle_screenshot, F.callback_query.data.startswith("send_screenshot_"))
    dp.callback_query.register(handle_callback, F.callback_query.data.in_([
        "self", "basic", "pro", "offer",
        "send_screenshot_basic", "send_screenshot_pro",
        "get_materials", "used_link"
    ]))
    dp.callback_query.register(handle_used_link, F.callback_query.data == "used_link")
    dp.callback_query.register(approve_user, lambda c: c.data.startswith("approve_"))