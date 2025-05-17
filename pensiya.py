import logging
import time
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from aiogram.filters import Command

API_TOKEN = '7964267404:AAGecVUXWNcf7joR-wM5Z9A92m7-HOkh0RM'
ADMIN_ID = 957724800

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

user_access = {}
user_tariffs = {}

# Кнопки
main_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Уровень САМОСТОЯТЕЛЬНЫЙ", callback_data="self")],
    [InlineKeyboardButton(text="Уровень БАЗОВЫЙ", callback_data="basic")],
    [InlineKeyboardButton(text="Уровень ПРО", callback_data="pro")],
    [InlineKeyboardButton(text="Публичная оферта", callback_data="offer")]
])

materials_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🏰 Получить материалы", callback_data="get_materials")]
])

def get_self_years_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Пенсия {year}", callback_data=f"year_{year}")] for year in range(2025, 2032)
    ])

def get_year_buttons(year):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Оплатить", url="https://pay.kaspi.kz/pay/vx2s6z0c")],
        [InlineKeyboardButton(text="📸 Отправить скриншот", callback_data=f"send_screenshot_{year}")]
    ])

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Добро пожаловать, Админ! Используйте /help для получения списка команд.")
    else:
        if message.from_user.id in user_access and user_access[message.from_user.id] > time.time():
            await message.answer("У вас уже есть доступ.", reply_markup=materials_keyboard)
        else:
            welcome_text = (
                "👋 *Добро пожаловать в бот “СВОЯ ПЕНСИЯ”* – твой персональный помощник на пути к достойной пенсии!\n"
                "Здесь ты найдёшь всё, чтобы понимать на какую пенсию ты можешь рассчитывать, как её увеличить и какие выплаты тебе положены именно в твоей ситуации. "
                "Получишь алгоритм расчета пенсии применительный к твоей ситуации.\n\n"

                "👉 *Внутри уже доступно:*\n"
                "1️⃣ Разборы пенсий в Казахстане: кто, когда и сколько может получить\n"
                "2️⃣ Доступ к закрытым материалам: текст, видео, фото — в зависимости от выбранного тарифа\n\n"

                "💰 *Уровни:*\n"
                "*САМОСТОЯТЕЛЬНЫЙ* — 10 000 тг\n"
                "*БАЗОВЫЙ* — 50 000 тг\n"
                "*ПРО* — 250 000 тг\n\n"

                "Ты можешь оплатить прямо здесь и отправить скриншот оплаты. После этого администратор активирует тебе доступ, и появится кнопка *ПОЛУЧИТЬ МАТЕРИАЛЫ*.\n\n"

                "Ты не один — давай разбираться вместе!\n"
                "Выбирай уровень, чтобы начать."
            )
            await message.answer(welcome_text, parse_mode="Markdown", reply_markup=main_keyboard)


@dp.message(Command("g"))
async def grant_access(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("Нет доступа.")
    args = message.text.split()
    if len(args) < 3:
        return await message.answer("Использование: /g [id] [basic/pro/2025-2031]")
    try:
        user_id = int(args[1])
        tariff = args[2].lower()
        if tariff not in ["basic", "pro"] + [str(y) for y in range(2025, 2032)]:
            return await message.answer("Тариф должен быть 'basic', 'pro' или '2025'-'2031'.")

        user_tariffs[user_id] = tariff

        if tariff == "basic":
            duration = 30 * 24 * 60 * 60
        elif tariff == "pro":
            duration = 60 * 24 * 60 * 60
        else:
            duration = 30

        user_access[user_id] = time.time() + duration

        await message.answer(f"Доступ выдан пользователю {user_id} ({tariff}) на {duration // 86400} дней.")
        await bot.send_message(
            user_id,
            f"✅ Доступ к материалам уровня {tariff.upper()} активирован на {duration // 86400} дней!",
            reply_markup=materials_keyboard
        )
    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await message.answer("Произошла ошибка.")


@dp.message(Command("revoke"))
async def revoke_access(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("Нет доступа.")

    args = message.text.split()
    if len(args) < 2:
        return await message.answer("Укажите ID пользователя.")

    try:
        user_id = int(args[1])
        if user_id in user_access:
            # Удаляем доступ
            del user_access[user_id]
            user_tariffs.pop(user_id, None)

            # Уведомление для пользователя
            await bot.send_message(user_id, "❌ Ваш доступ был отозван. Теперь вы не можете получать материалы.")

            # Уведомление для администратора
            await bot.send_message(ADMIN_ID, f"Доступ пользователя {user_id} был отозван.")

            await message.answer(f"Доступ для пользователя {user_id} отозван.")
        else:
            await message.answer("У пользователя нет доступа.")
    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await message.answer("Произошла ошибка.")


@dp.message(Command("status"))
async def check_status(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("Нет доступа.")

    args = message.text.split()
    if len(args) < 2:
        return await message.answer("Укажите ID пользователя.")

    try:
        user_id = int(args[1])
        if user_id in user_access and user_access[user_id] > time.time():
            remaining_seconds = user_access[user_id] - time.time()
            days = int(remaining_seconds // (24 * 60 * 60))
            tariff = user_tariffs.get(user_id)

            if tariff:
                await message.answer(
                    f"✅ У пользователя {user_id} есть доступ ({tariff.upper()}). Осталось дней: {days}."
                )
            else:
                await message.answer(
                    f"✅ У пользователя {user_id} есть доступ. Осталось дней: {days}, но тариф не указан."
                )
        else:
            await message.answer("❌ Доступа нет или он истек.")

    except Exception as e:
        logging.error(f"\u041e\u0448\u0438\u0431\u043a\u0430: {e}")
        await message.answer("Ошибка при проверке статуса.")


@dp.message(Command("help"))
async def help_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("Нет доступа.")
    await message.answer("""
/g [id] [basic/pro/2025-2031] - выдать доступ
/revoke [id] - отозвать доступ
/status [id] - статус доступа
/users - показать всех с доступом
/help - команды
    """)


@dp.message(Command("users"))
async def show_users(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("Нет доступа.")
    if not user_access:
        return await message.answer("Пока нет пользователей с доступом.")
    lines = [
        f"{uid} - до {time.ctime(exp)} ({user_tariffs.get(uid, 'неизвестно')})"
        for uid, exp in user_access.items() if exp > time.time()
    ]
    await message.answer("\n".join(lines))

@dp.callback_query(lambda c: c.data.startswith("year_"))
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

@dp.callback_query(lambda c: c.data.startswith("send_screenshot_"))
async def handle_year_screenshot(call: types.CallbackQuery):
    year = call.data.split("_")[2]
    user_tariffs[call.from_user.id] = year
    await call.message.answer("📸 Пожалуйста, отправьте скриншот для проверки.")

@dp.callback_query(
    lambda c: c.data in ["self", "basic", "pro", "offer", "send_screenshot_basic", "send_screenshot_pro", "get_materials"])
async def handle_callback(call: types.CallbackQuery):
    data = call.data
    user_id = call.from_user.id

    if data == "self":
        await call.message.answer("Выберите год вашего выхода на пенсию:", reply_markup=get_self_years_keyboard())
        return

    if data == "basic":
        user_tariffs[user_id] = "basic"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Оплатить", url="https://pay.kaspi.kz/pay/vx2s6z0c")],
            [InlineKeyboardButton(text="📸 Отправить скриншот", callback_data="send_screenshot_basic")]
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
        user_tariffs[user_id] = "pro"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Оплатить", url="https://pay.kaspi.kz/pay/vx2s6z0c")],
            [InlineKeyboardButton(text="📸 Отправить скриншот", callback_data="send_screenshot_pro")]
        ])
        await call.message.answer("❌ Временно недоступно", reply_markup=keyboard)

    elif data == "offer":
    pdf_path = "Публичная оферта.pdf"  # путь к вашему PDF-файлу

    # Отправляем файл пользователю
    await call.message.answer_document(open(pdf_path, "rb"))

    elif data == "get_materials":
        if user_id not in user_access or user_access[user_id] < time.time():
            return await call.message.answer("❌ У вас нет активного доступа.")
        else:
            tariff = user_tariffs.get(user_id)

            # Словарь ссылок для каждого тарифа
            links = {
                "basic": "https://t.me/+HxDdgxzq-9tiNDAy",
                "pro": "https://t.me/pro_channel",
                "2025": "https://t.me/+AaxT4exaNP40NGE6",
                "2026": "https://t.me/+RIvK4Xqzvis1ZjJi",
                "2027": "https://t.me/+ZxN5WrOTCNlhMDIy",
                "2028": "https://t.me/+F5rkfcWZn4AxZTBi",
                "2029": "https://t.me/+lAKvIyr6znw1ZDky",
                "2030": "https://t.me/+VdBjEj-W9oAyZmEy",
                "2031": "https://t.me/+slHyJgK8t1k0MWNi"
            }

            link = links.get(tariff)
            if link:
                await call.message.answer(f"🔗 Ссылка на канал: {link}")
            else:
                await call.message.answer("❌ Не удалось определить ссылку для вашего тарифа.")

    elif data.startswith("send_screenshot"):
        await call.message.answer("📸 Пожалуйста, отправьте скриншот для проверки.")


@dp.message(lambda msg: msg.photo)
async def handle_photo(message: types.Message):
    user = message.from_user
    tariff = user_tariffs.get(user.id, "не выбран")
    info = (
        f"📸 Скриншот от пользователя:\n"
        f"🆔 ID: {user.id}\n"
        f"👤 Username: @{user.username if user.username else 'Без username'}\n"
        f"💳 Уровень: {tariff.upper() if tariff else 'не выбран'}"
    )
    await message.answer(f"Спасибо за скриншот! Вы выбрали уровень: {tariff.upper()}")
    await bot.send_message(ADMIN_ID, info)
    await bot.send_photo(chat_id=ADMIN_ID, photo=message.photo[-1].file_id, caption="Скриншот оплаты")


# 🔁 Проверка доступа каждые 10 сек
GROUP_IDS = [-1002583988789, -1002529607781, -1002611068580, -1002607289832, -1002560662894, -1002645685285, -1002529375771, -1002262602915]  # список ID групп (можно получить через @userinfobot)

async def check_access_periodically():
    while True:
        current_time = time.time()
        expired_users = [uid for uid, expire_time in user_access.items() if expire_time <= current_time]

        for user_id in expired_users:
            tariff = user_tariffs.get(user_id, "неизвестно")

            # Удаление из групп
            for group_id in GROUP_IDS:
                try:
                    await bot.ban_chat_member(group_id, user_id)  # бан
                    await bot.unban_chat_member(group_id, user_id)  # сразу разбан, чтобы можно было вернуться
                    logging.info(f"Пользователь {user_id} удалён из группы {group_id}")
                except Exception as e:
                    logging.warning(f"Не удалось удалить пользователя {user_id} из группы {group_id}: {e}")

            # Уведомление пользователя
            try:
                await bot.send_message(user_id, "❌ Ваш доступ истёк. Вы были удалены из группы.")
            except:
                pass

            # Уведомление администратора
            try:
                await bot.send_message(
                    ADMIN_ID,
                    f"⛔️ Пользователь {user_id} был удалён из групп, доступ истёк ({tariff})."
                )
            except:
                pass

            # Очистка данных
            user_access.pop(user_id, None)
            user_tariffs.pop(user_id, None)

        await asyncio.sleep(5)


async def main():
    asyncio.create_task(check_access_periodically())
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
