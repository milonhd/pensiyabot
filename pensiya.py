import logging
import time
import asyncio
import os
from aiogram import F
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from aiogram.filters import Command
from aiogram.types import FSInputFile
import aiopg

# Конфигурация для PostgreSQL
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    # Локальная конфигурация для тестирования
    DATABASE_URL = "postgres://username:password@localhost:5432/telegrambot"

API_TOKEN = '7964267404:AAGecVUXWNcf7joR-wM5Z9A92m7-HOkh0RM'
ADMIN_ID = 957724800

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Подключение к базе данных
async def create_pool():
    return await aiopg.create_pool(DATABASE_URL)

# Создание таблиц (если они еще не созданы)
async def init_db():
    pool = await create_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            # Таблица для хранения доступов пользователей
            await cur.execute("""
            CREATE TABLE IF NOT EXISTS user_access (
                user_id BIGINT PRIMARY KEY,
                expire_time BIGINT,
                tariff VARCHAR(20)
            )
            """)
    pool.close()
    await pool.wait_closed()

# Функции для работы с базой данных
async def set_user_access(user_id, expire_time, tariff):
    pool = await create_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
            INSERT INTO user_access (user_id, expire_time, tariff)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE 
            SET expire_time = EXCLUDED.expire_time, tariff = EXCLUDED.tariff
            """, (user_id, expire_time, tariff))
    pool.close()
    await pool.wait_closed()

async def get_user_access(user_id):
    pool = await create_pool()
    result = None, None
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT expire_time, tariff FROM user_access WHERE user_id = %s", (user_id,))
            row = await cur.fetchone()
            if row:
                result = row[0], row[1]
    pool.close()
    await pool.wait_closed()
    return result

async def delete_user_access(user_id):
    pool = await create_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM user_access WHERE user_id = %s", (user_id,))
    pool.close()
    await pool.wait_closed()

async def get_all_active_users():
    pool = await create_pool()
    result = []
    current_time = time.time()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT user_id, expire_time, tariff FROM user_access WHERE expire_time > %s", (current_time,))
            result = await cur.fetchall()
    pool.close()
    await pool.wait_closed()
    return result

async def get_expired_users():
    pool = await create_pool()
    result = []
    current_time = time.time()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT user_id, tariff FROM user_access WHERE expire_time <= %s", (current_time,))
            result = await cur.fetchall()
    pool.close()
    await pool.wait_closed()
    return result


# Кнопки (не изменены)
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
    user = message.from_user
    name = user.first_name or "Пользователь"
    
    if message.from_user.id == ADMIN_ID:
        await message.answer("Добро пожаловать, Админ! Используйте /help для получения списка команд.")
    else:
        expire_time, _ = await get_user_access(message.from_user.id)
        if expire_time and expire_time > time.time():
            await message.answer(f"👋 Добро пожаловать, {name}! У вас уже есть доступ.", reply_markup=materials_keyboard)
        else:
            welcome_text = (
               f"👋 *Добро пожаловать, {name}, в бот «СВОЯ ПЕНСИЯ»* – твой персональный помощник на пути к достойной пенсии!\n"
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

        if tariff == "basic":
            duration = 30 * 24 * 60 * 60
        elif tariff == "pro":
            duration = 60 * 24 * 60 * 60
        else:
            duration = 7 * 24 * 60 * 60  

        expire_time = time.time() + duration
        await set_user_access(user_id, expire_time, tariff)

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
        expire_time, _ = await get_user_access(user_id)
        
        if expire_time:
            # Удаляем доступ
            await delete_user_access(user_id)

            # Уведомление для пользователя
            await bot.send_message(user_id, "❌ Ваш доступ был отозван. Теперь вы не можете получать материалы.")

            # Уведомление для администратора
            await bot.send_message(ADMIN_ID, f"Доступ пользователя {user_id} был отозван.")

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
        expire_time, tariff = await get_user_access(user_id)
        
        if expire_time and expire_time > time.time():
            remaining_seconds = expire_time - time.time()
            days = int(remaining_seconds // (24 * 60 * 60))

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
        logging.error(f"Ошибка: {e}")
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
    
    active_users = await get_all_active_users()
    if not active_users:
        return await message.answer("Пока нет пользователей с доступом.")
    
    lines = [
        f"{uid} - до {time.ctime(exp)} ({tariff})"
        for uid, exp, tariff in active_users
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
    # Сохраняем выбранный тариф в базе данных как "temp_tariff"
    await set_user_access(call.from_user.id, None, year)  
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
        await set_user_access(user_id, None, "basic")  # Временно сохраняем выбор
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
        await set_user_access(user_id, None, "pro")  # Временно сохраняем выбор
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Оплатить", url="https://pay.kaspi.kz/pay/vx2s6z0c")],
            [InlineKeyboardButton(text="📸 Отправить скриншот", callback_data="send_screenshot_pro")]
        ])
        await call.message.answer("❌ Временно недоступно", reply_markup=keyboard)

    elif data == "offer":
        pdf_path = "oferta.pdf"  # убедись, что путь и имя файла корректны
        try:
            document = FSInputFile(pdf_path)
            await call.message.answer_document(document)
        except Exception as e:
            await call.message.answer("⚠️ Ошибка при отправке файла: " + str(e))
    
    elif data == "get_materials":
        expire_time, tariff = await get_user_access(user_id)
        if not expire_time or expire_time < time.time():
            return await call.message.answer("❌ У вас нет активного доступа.")

        # Сопоставление тарифов и ID групп
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
            # Создаем временную ссылку (15 секунд)
            invite = await bot.create_chat_invite_link(
                chat_id=chat_id,
                member_limit=1,
                expire_date=int(time.time()) + 15,
                creates_join_request=False
            )
        
            # Отправляем сообщение со ссылкой
            msg = await call.message.answer(
                f"🔐 Ваша персональная ссылка:\n{invite.invite_link}"
            )
            
            # Удаляем сообщение через 15 секунд
            await asyncio.sleep(15)
            try:
                await msg.delete()
            except Exception as e:
                logging.error(f"Не удалось удалить сообщение: {e}")
            
        except Exception as e:
            logging.error(f"Ошибка создания ссылки для чата {chat_id}: {e}")
            await call.message.answer("⚠️ Ошибка при создании ссылки.")

@dp.message(lambda msg: msg.photo)
async def handle_photo(message: types.Message):
    user = message.from_user
    _, tariff = await get_user_access(user.id)
    
    if not tariff:
        tariff = "не выбран"
        
    info = (
        f"📸 Скриншот от пользователя:\n"
        f"🆔 ID: {user.id}\n"
        f"👤 Username: @{user.username if user.username else 'Без username'}\n"
        f"💳 Уровень: {tariff.upper() if tariff else 'не выбран'}"
    )
    await message.answer(f"Спасибо за скриншот! Вы выбрали уровень: {tariff.upper()}")
    approve_button = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Выдать доступ", callback_data=f"approve_{user.id}")]
    ])
    await bot.send_message(ADMIN_ID, info, reply_markup=approve_button)
    await bot.send_photo(chat_id=ADMIN_ID, photo=message.photo[-1].file_id, caption="Скриншот оплаты")

# Удаление сообщений о входе новых участников
@dp.message(F.new_chat_members)
async def remove_join_message(message: types.Message):
    try:
        await message.delete()
    except Exception as e:
        logging.warning(f"Не удалось удалить join-сообщение: {e}")

# Удаление сообщений о выходе участников
@dp.message(F.left_chat_member)
async def remove_leave_message(message: types.Message):
    try:
        await message.delete()
    except Exception as e:
        logging.warning(f"Не удалось удалить leave-сообщение: {e}")


# 🔁 Проверка доступа каждые 10 сек
GROUP_IDS = [-1002583988789, -1002529607781, -1002611068580, -1002607289832, -1002560662894, -1002645685285, -1002529375771, -1002262602915]  # список ID групп

async def check_access_periodically():
    while True:
        try:
            expired_users = await get_expired_users()

            for user_id, tariff in expired_users:
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
                except Exception as e:
                    logging.warning(f"Не удалось отправить уведомление пользователю {user_id}: {e}")

                # Уведомление администратора
                try:
                    await bot.send_message(
                        ADMIN_ID,
                        f"⛔️ Пользователь {user_id} был удалён из групп, доступ истёк ({tariff})."
                    )
                except Exception as e:
                    logging.warning(f"Не удалось отправить уведомление администратору: {e}")

                # Удаляем из базы данных
                await delete_user_access(user_id)

        except Exception as e:
            logging.error(f"Ошибка в проверке доступа: {e}")

        await asyncio.sleep(10)

@dp.callback_query(lambda c: c.data.startswith("approve_"))
async def approve_user(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Недостаточно прав")

    user_id = int(call.data.split("_")[1])
    _, tariff = await get_user_access(user_id)

    if not tariff:
        return await call.answer("❌ У пользователя не выбран тариф. Сначала выберите тариф!")

    # Длительность доступа
    if tariff == "basic":
        duration = 30 * 86400
    elif tariff == "pro":
        duration = 60 * 86400
    elif tariff in [str(y) for y in range(2025, 2032)]:
        duration = 7 * 86400
    else:
        return await call.answer("❌ Неизвестный тариф.")

    # Сохраняем
    expire_time = time.time() + duration
    await set_user_access(user_id, expire_time, tariff)

    # Лог (сохраняем в файл)
    with open("access_log.txt", "a", encoding="utf-8") as f:
        f.write(f"{user_id} | {tariff} | {time.ctime()} | {duration // 86400} дней\n")

    # Уведомление пользователю
    await bot.send_message(user_id, f"✅ Доступ уровня {tariff.upper()} выдан на {duration // 86400} дней!", reply_markup=materials_keyboard)

    # Убираем кнопку
    await call.message.edit_reply_markup(reply_markup=None)
    await call.answer("Доступ выдан.")

async def check_subscriptions():
    while True:
        users = await get_all_active_users()
        for user_id, expire_time, _ in users:
            if (expire_time - time.time()) < 86400 * 3:  # За 3 дня до истечения
                await bot.send_message(
                    user_id,
                    f"⚠️ Ваш доступ истекает через 3 дня!",
                    reply_markup=main_keyboard
                )
        await asyncio.sleep(3600)  # Проверка каждый час

async def main():
    # Инициализация базы данных при запуске
    await init_db()
    # Запуск периодической проверки доступов
    asyncio.create_task(check_access_periodically())
    # Запуск бота
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
