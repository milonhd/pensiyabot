import logging
import time
import asyncio
import os
import pdfplumber
import re
from aiogram import F
from datetime import datetime, timedelta
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from aiogram.filters import Command
from aiogram.enums import ChatType
from aiogram.types import FSInputFile
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import BotCommandScopeAllPrivateChats
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from database import DATABASE_URL, create_db_pool, close_db_pool, init_db, get_db_connection
from reviews import register_reviews_handlers

load_dotenv()

API_TOKEN = os.environ.get('API_TOKEN')
if not API_TOKEN:
    logging.error("API_TOKEN был не найден.")
    exit(1) 

ADMIN_ID = 957724800

GROUP_IDS = [-1002583988789, -1002529607781, -1002611068580, -1002607289832, -1002560662894, -1002645685285, -1002529375771, -1002262602915]
RECEIPT_DIR = "/app/receipts"

os.makedirs(RECEIPT_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler(timezone="UTC")

register_reviews_handlers(dp, bot)

class BroadcastStates(StatesGroup):
    waiting_content = State()
    waiting_confirm = State()
    waiting_time = State()

db_pool = None

main_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Уровень САМОСТОЯТЕЛЬНЫЙ", callback_data="self")],
    [InlineKeyboardButton(text="Уровень БАЗОВЫЙ", callback_data="basic")],
    [InlineKeyboardButton(text="Уровень ПРО", callback_data="pro")],
])

materials_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🏰 Получить материалы", callback_data="get_materials"),
    [InlineKeyboardButton(text="📝 Оставить отзыв", callback_data=f"start_review_{user_id}")]
])

def get_self_years_keyboard():
    builder = InlineKeyboardBuilder()
    for year in range(2025, 2032):
        builder.button(text=f"Пенсия {year}", callback_data=f"year_{year}")
    builder.button(text="◀️ Назад", callback_data="menu")
    builder.adjust(2)
    return builder.as_markup()

@dp.callback_query(F.data == "menu")
async def handle_back_to_menu(call: types.CallbackQuery):
    try:
        await call.message.edit_text(
            "👇 Выберите желаемый уровень:",
            reply_markup=main_keyboard
        )
        await call.answer()
    except Exception as e:
        logging.error(f"Ошибка в обработчике 'Назад': {e}")

def get_year_buttons(year):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Оплатить", url="https://pay.kaspi.kz/pay/vx2s6z0c")],
        [InlineKeyboardButton(text="📄 Отправить чек", callback_data=f"send_screenshot_{year}")]
    ])

@dp.message(Command("start"), F.chat.type == ChatType.PRIVATE)
async def cmd_start(message: types.Message):
    await save_user(message.from_user)
    user = message.from_user
    name = user.first_name or "Пользователь"

    main_kb = ReplyKeyboardBuilder()
    main_kb.button(text="📄 Публичная оферта")
    main_kb.button(text="📞 Поддержка")
    main_kb.button(text="👤 Мой профиль")
    
    if message.from_user.id == ADMIN_ID:
        main_kb.button(text="📢 Рассылка")
    
    main_kb.adjust(2)  
    
    if message.from_user.id == ADMIN_ID:
        await message.answer("Добро пожаловать, Админ! Используйте /help для получения списка команд.",  reply_markup=main_kb.as_markup(resize_keyboard=True, one_time_keyboard=False))
    else:
        expire_time, _ = await get_user_access(message.from_user.id)
        if expire_time and expire_time > datetime.now():
            await message.answer(f"👋 Добро пожаловать, {name}! У вас уже есть доступ.", reply_markup=main_kb.as_markup(resize_keyboard=True, one_time_keyboard=False))
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

                "Ты можешь оплатить прямо здесь и отправить чек оплаты. После этого администратор активирует тебе доступ, и появится кнопка *ПОЛУЧИТЬ МАТЕРИАЛЫ*.\n\n"

                "Ты не один — давай разбираться вместе!\n"
            )
            await message.answer(welcome_text, parse_mode="Markdown", reply_markup=main_kb.as_markup(resize_keyboard=True, one_time_keyboard=False))
            await message.answer(
                "👇 Выберите желаемый уровень:",
                reply_markup=main_keyboard  
            )


@dp.message(Command("g"), F.chat.type == ChatType.PRIVATE)
async def grant_access(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Нет доступа.")

    args = message.text.split()
    if len(args) < 3:
        return await message.answer("Использование: /g [id] [basic/pro/2025-2031]")

    try:
        user_id = int(args[1])
        tariff = args[2].lower()

        duration_map = {
            "self": 7,
            "basic": 30,
            "pro": 60,
            **{str(year): 7 for year in range(2025, 2032)} 
        }

        if tariff not in duration_map:
            return await message.answer("❌ Неверный тариф. Допустимые: basic, pro, 2025-2031")

        duration_days = duration_map[tariff]

        success = await set_user_access(user_id, duration_days, tariff)
        
        if success:
            expire_date = (datetime.now() + timedelta(days=duration_days)).strftime("%d.%m.%Y %H:%M")
            await message.answer(f"✅ Пользователю {user_id} выдан доступ до {expire_date} ({tariff.upper()})")
            await bot.send_message(user_id, f"✅ Доступ к материалам уровня {tariff.upper()} активирован до {expire_date}!",
            reply_markup=materials_keyboard
        )
        else:
            await message.answer("❌ Ошибка при выдаче доступа")

    except Exception as e:
        logging.error(f"Ошибка в /g: {e}")
        await message.answer("❌ Проверьте правильность аргументов")

@dp.message(Command("revoke"), F.chat.type == ChatType.PRIVATE)
async def revoke_access(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Нет доступа.")

    args = message.text.split()
    if len(args) < 2:
        return await message.answer("Укажите ID пользователя.")

    try:
        user_id = int(args[1])
        expire_time, _ = await get_user_access(user_id)
        
        if expire_time:
            await revoke_user_access(user_id)
            await bot.send_message(user_id, "❌ Ваш доступ был отозван. Теперь вы не можете получать материалы.")

            await bot.send_message(ADMIN_ID, f"Доступ пользователя {user_id} был отозван.")

            for group_id in GROUP_IDS:
                try:
                    await bot.ban_chat_member(group_id, user_id)
                    await bot.unban_chat_member(group_id, user_id)  
                    logging.info(f"Пользователь {user_id} удалён из группы {group_id}")
                except Exception as e:
                    logging.error(f"Не удалось удалить пользователя из группы {group_id}: {e}")
        
        else:
            await message.answer("У пользователя нет доступа.")
    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await message.answer("Произошла ошибка.")

@dp.message(Command("status"), F.chat.type == ChatType.PRIVATE)
async def check_status(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Нет доступа.")

    args = message.text.split()
    if len(args) < 2:
        return await message.answer("Укажите ID пользователя.")

    try:
        user_id = int(args[1])
        expire_time, tariff = await get_user_access(user_id)
        
        if expire_time and expire_time > datetime.now():
            remaining = expire_time - datetime.now()
            days = remaining.days
            formatted_time = expire_time.strftime('%H:%M %d.%m.%Y')

            if tariff:
                await message.answer(
                    f"✅ У пользователя {user_id} есть доступ ({tariff.upper()}). Истекает: {formatted_time}."
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

@dp.message(Command("help"), F.chat.type == ChatType.PRIVATE)
async def help_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Нет доступа.")
    await message.answer("""
/g [id] [basic/pro/2025-2031] - выдать доступ
/revoke [id] - отозвать доступ
/status [id] - статус доступа
/stats - статистика бота
/help - команды
    """)

@dp.message(Command("stats"), F.chat.type == ChatType.PRIVATE)
async def show_stats(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Нет доступа.")
    
    try:
        stats = await get_stats()
     
        tariff_text = ""
        for tariff, count in stats['tariff_stats']:
            if tariff:
                tariff_display = {
                    'basic': 'БАЗОВЫЙ',
                    'pro': 'ПРО', 
                    'self': 'САМОСТОЯТЕЛЬНЫЙ'
                }.get(tariff, f'Год {tariff}' if tariff.isdigit() else tariff.upper())
                tariff_text += f"  • {tariff_display}: {count}\n"
      
        popular_text = ""
        for tariff, count in stats['popular_tariffs'][:5]:  
            if tariff:
                tariff_display = {
                    'basic': 'БАЗОВЫЙ',
                    'pro': 'ПРО',
                    'self': 'САМОСТОЯТЕЛЬНЫЙ'
                }.get(tariff, f'Год {tariff}' if tariff.isdigit() else tariff.upper())
                popular_text += f"  • {tariff_display}: {count} чеков\n"
        
        stats_text = f"""📊 **Статистика бота**

👥 **Пользователи:**
  • Всего зарегистрировано: {stats['total_users']}
  • С активным доступом: {stats['active_users']}
  • Новых за месяц: {stats['new_users_30d']}
  • Активных за неделю: {stats['active_7d']}

💳 **Активные тарифы:**
{tariff_text if tariff_text else '  • Нет активных тарифов'}

📄 **Чеки:**
  • Загружено за месяц: {stats['receipts_30d']}

🔥 **Популярные тарифы (месяц):**
{popular_text if popular_text else '  • Нет данных'}

📈 **Конверсия:**
  • Активация от регистрации: {round(stats['active_users']/stats['total_users']*100 if stats['total_users'] > 0 else 0, 1)}%
  • Активность за неделю: {round(stats['active_7d']/stats['total_users']*100 if stats['total_users'] > 0 else 0, 1)}%
"""
        
        await message.answer(stats_text, parse_mode="Markdown")
        
    except Exception as e:
        logging.error(f"Ошибка получения статистики: {e}")
        await message.answer("❌ Ошибка при получении статистики")

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

@dp.callback_query(F.data.startswith("send_screenshot_"))
async def handle_screenshot(call: types.CallbackQuery):
    user_id = call.from_user.id
    expire_time, current_tariff = await get_user_access(user_id)
 
    if expire_time and expire_time > datetime.now():
        await call.answer("❗ У вас уже есть активный доступ!", show_alert=True)
        return
    
    selected_tariff_or_year = call.data.split("_")[2]
    
    duration_map = {
        "basic": 30,
        "pro": 60,
        **{str(year): 7 for year in range(2025, 2032)} 
    }
 
    duration_days = duration_map.get(selected_tariff_or_year, 7)
    
    await set_user_access(user_id, duration_days, selected_tariff_or_year)
  
    await call.message.answer(
        "📄 Пожалуйста, отправьте PDF-файл фискального чека из Kaspi!\n\n"
        "📌 Как получить чек:\n"
        "1. После оплаты в Kaspi нажмите «Показать чек об оплате»\n"
        "2. Нажмите «Поделиться»\n"
        "3. Отправьте чек в этот чат\n\n"
    )

@dp.callback_query(
    F.data.in_([
        "self", "basic", "pro", "offer",
        "send_screenshot_basic", "send_screenshot_pro",  
        "get_materials", "used_link"
    ])
)
async def handle_callback(call: types.CallbackQuery):
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
        if not expire_time or expire_time < datetime.now():
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
                expire_date=int(time.time()) + 20,
                creates_join_request=False
            )
  
            msg = await call.message.answer(
                f"🔐 Ваша персональная ссылка (исчезнет спустя 20 секунд):\n{invite.invite_link}"
            )
            
            await asyncio.sleep(20)
            try:
                await msg.delete()
            except Exception as e:
                logging.error(f"Не удалось удалить сообщение: {e}")
            
        except Exception as e:
            logging.error(f"Ошибка создания ссылки для чата {chat_id}: {e}")
            await call.message.answer("⚠️ Ошибка при создании ссылки.")

@dp.callback_query(F.data == "used_link")
async def handle_used_link(call: types.CallbackQuery):
    await call.answer("Вы уже использовали эту ссылку", show_alert=True)

async def parse_kaspi_receipt(pdf_path: str):
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = "\n".join(page.extract_text() for page in pdf.pages)
            
            data = {
                "amount": float(re.search(r"(\d+)\s*₸", text).group(1)) if re.search(r"(\d+)\s*₸", text) else None,
                "iin": re.search(r"ИИН/БИН продавца\s*(\d+)", text).group(1) if re.search(r"ИИН/БИН продавца\s*(\d+)", text) else None,
                "check_number": re.search(r"№ чека\s*(\S+)", text).group(1) if re.search(r"№ чека\s*(\S+)", text) else None,
                "fp": re.search(r"ФП\s*(\d+)", text).group(1) if re.search(r"ФП\s*(\d+)", text) else None,
                "date_time": re.search(r"Дата и время\s*(?:по Астане)?\s*(\d{2}\.\d{2}\.\d{4} \d{2}:\d{2})"
, text).group(1) if re.search(r"Дата и время\s*(?:по Астане)?\s*(\d{2}\.\d{2}\.\d{4} \d{2}:\d{2})"
, text) else None,
                "buyer_name": re.search(r"ФИО покупателя\s*(.+)", text).group(1).strip() if re.search(r"ФИО покупателя\s*(.+)", text) else None
            }
            return data
    except Exception as e:
        logging.error(f"Ошибка парсинга PDF: {e}")
        return None

@dp.message(F.document, F.chat.type == ChatType.PRIVATE)
async def handle_document(message: types.Message):
    logging.info(f"Получен документ: {message.document.file_name}")
    user = message.from_user
    
    if not message.document.mime_type == 'application/pdf':
        return await message.answer("❌ Пожалуйста, отправьте PDF-файл чека из Kaspi")

    file_id = message.document.file_id
    if await check_duplicate_file(file_id):
        return await message.answer("❌ Этот чек уже был загружен ранее")
  
    file_path = os.path.join(RECEIPT_DIR, f"{user.id}_{message.document.file_name}")
    await bot.download(file=await bot.get_file(file_id), destination=file_path)

    receipt_data = await parse_kaspi_receipt(file_path)
    
    if not receipt_data:
        return await message.answer("❌ Не удалось прочитать чек. Убедитесь, что отправлен корректный файл.")
  
    required_fields = ["amount", "check_number", "fp", "date_time", "iin", "buyer_name"]
    missing_fields = [field for field in required_fields if receipt_data.get(field) is None]
    
    if missing_fields:
        return await message.answer(
            f"❌ В чеке отсутствуют обязательные данные: {', '.join(missing_fields)}.\n"
            "Убедитесь, что чек содержит всю необходимую информацию."
        )
    
    try:
        date_time = datetime.strptime(receipt_data["date_time"], "%d.%m.%Y %H:%M")
    except ValueError as e:
        return await message.answer(f"❌ Ошибка в формате даты чека: {e}")

    await message.answer(
        f"📄 Данные чека:\n"
        f"ИИН: {receipt_data['iin']}\n"
        f"Сумма: {receipt_data['amount']}\n"
        f"Номер чека: {receipt_data['check_number']}\n"
        f"Дата: {receipt_data['date_time']}"
    )
    
    expire_time, tariff = await get_user_access(user.id)
    required_amounts = {
        "self": 10000,
        "basic": 50000,
        "pro": 250000,
        "2025": 10000,
        "2026": 10000,
        "2027": 10000,
        "2028": 10000,
        "2029": 10000,
        "2030": 10000,
        "2031": 10000
    }

    errors = []
    if receipt_data["iin"] != "620613400018":
        errors.append("ИИН продавца не совпадает")
        
    if receipt_data["amount"] != required_amounts.get(tariff, 0):
        errors.append(f"Сумма не соответствует тарифу {tariff}")

    if errors:
        return await message.answer("❌ Ошибки в чеке:\n" + "\n".join(errors))

    if not await save_receipt(
        user_id=user.id,
        amount=receipt_data["amount"],
        check_number=receipt_data["check_number"],
        fp=receipt_data["fp"],
        date_time=date_time,
        buyer_name=receipt_data["buyer_name"],
        file_id=file_id
    ):
        return await message.answer("❌ Ошибка при сохранении чека")

    if tariff in ["self", "basic", "pro"] + [str(y) for y in range(2025, 2032)]:
        duration = {
            "self": 7,
            "basic": 30,
            "pro": 60,
            **{str(y): 7 for y in range(2025, 2032)}
        }.get(tariff, 7) * 86400
        
        await set_user_access(user.id, time.time() + duration, tariff)
        await message.answer(
            f"✅ Доступ уровня {tariff.upper()} активирован на {duration//86400} дней!",
            reply_markup=materials_keyboard
        )

    info = (
        f"📄 Фискальный чек от пользователя:\n"
        f"🆔 ID: {user.id}\n"
        f"👤 Username: @{user.username or 'Без username'}\n"
        f"💳 Уровень: {tariff.upper() if tariff else 'не выбран'}\n"
        f"📝 Файл: {message.document.file_name}"
    )
    
    await bot.send_message(ADMIN_ID, info)
    await bot.send_document(ADMIN_ID, message.document.file_id)
    
@dp.message(F.new_chat_members)
async def remove_join_message(message: types.Message):
    try:
        await message.delete()
    except Exception as e:
        logging.warning(f"Не удалось удалить join-сообщение: {e}")

@dp.message(F.left_chat_member)
async def remove_leave_message(message: types.Message):
    try:
        await message.delete()
    except Exception as e:
        logging.warning(f"Не удалось удалить leave-сообщение: {e}")

GROUP_IDS = [-1002583988789, -1002529607781, -1002611068580, -1002607289832, -1002560662894, -1002645685285, -1002529375771, -1002262602915]  

async def check_access_periodically():
    while True:
        try:
            expired_users = await get_expired_users()

            for user_id, tariff in expired_users:
                await revoke_user_access(user_id)
                
                for group_id in GROUP_IDS:
                    try:
                        await bot.ban_chat_member(group_id, user_id) 
                        await bot.unban_chat_member(group_id, user_id)  
                        logging.info(f"Пользователь {user_id} удалён из группы {group_id}")
                    except Exception as e:
                        logging.warning(f"Не удалось удалить пользователя {user_id} из группы {group_id}: {e}")

                try:
                    await bot.send_message(user_id, "❌ Ваш доступ истёк. Вы были удалены из группы.")
                except Exception as e:
                    logging.warning(f"Не удалось отправить уведомление пользователю {user_id}: {e}")

                try:
                    await bot.send_message(
                        ADMIN_ID,
                        f"⛔️ Пользователь {user_id} был удалён из групп, доступ истёк ({tariff})."
                    )
                except Exception as e:
                    logging.warning(f"Не удалось отправить уведомление администратору: {e}")

                await revoke_user_access(user_id)

        except Exception as e:
            logging.error(f"Ошибка в проверке доступа: {e}")

        await asyncio.sleep(10)

@dp.callback_query(lambda c: c.data.startswith("approve_"))
async def approve_user(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Недостаточно прав")

    user_id = int(call.data.split("_")[1])
    _, tariff = await get_user_access(user_id)

    global db_pool  
    if not db_pool:
        await create_db_pool()

    async with db_pool.acquire() as conn:  
        async with conn.cursor() as cur:
                await cur.execute("SELECT 1 FROM fiscal_checks WHERE user_id = %s", (user_id,))
                if not await cur.fetchone():
                    return await call.answer("❌ У пользователя нет подтвержденного чека")

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

    expire_time = datetime.now() + timedelta(seconds=duration)
    await set_user_access(user.id, expire_time, tariff)

    with open("access_log.txt", "a", encoding="utf-8") as f:
        f.write(f"{user_id} | {tariff} | {time.ctime()} | {duration // 86400} дней\n")

    await bot.send_message(user_id, f"✅ Доступ уровня {tariff.upper()} выдан на {duration // 86400} дней!", reply_markup=materials_keyboard)

    await call.message.edit_reply_markup(reply_markup=None)
    await call.answer("Доступ выдан.")

async def check_subscriptions():
    while True:
        users = await get_all_active_users()
        for user_id, expire_time, _ in users:
            if (expire_time - time.time()) < 86400 * 3: 
                await bot.send_message(
                    user_id,
                    f"⚠️ Ваш доступ истекает через 3 дня!",
                    reply_markup=main_keyboard
                )
        await asyncio.sleep(3600) 

@dp.message(F.text == "👤 Мой профиль", F.chat.type == ChatType.PRIVATE)
async def handle_profile(message: types.Message):
    await save_user(message.from_user) 
    
    expire_time, tariff = await get_user_access(message.from_user.id)
    user = message.from_user
    
    profile_text = (
        f"👤 <b>Ваш профиль</b>\n\n"
        f"🆔 ID: {user.id}\n"
        f"👤 Имя: {user.full_name}\n"
        f"📅 Дата регистрации: {datetime.now().strftime('%d.%m.%Y')}\n\n"
    )
    
    if expire_time and expire_time > datetime.now():
        expire_date = expire_time.strftime("%d.%m.%Y %H:%M")
        profile_text += (
            f"✅ <b>Подписка активна</b>\n"
            f"📌 Уровень: {tariff.upper() if tariff else 'Не указан'}\n"
            f"📆 Истекает: {expire_date}"
        )
    else:
        profile_text += "❌ <b>Подписка неактивна</b>\n\n👉 Выберите уровень командой /start"
    
    await message.answer(profile_text, parse_mode="HTML")

@dp.message(F.text == "📄 Публичная оферта", F.chat.type == ChatType.PRIVATE)
async def handle_offer_button(message: types.Message):
    pdf_path = "oferta.pdf"
    try:
        document = FSInputFile(pdf_path)
        await message.answer_document(document)
    except Exception as e:
        await message.answer("⚠️ Ошибка при отправке файла: " + str(e))

@dp.message(F.text == "📞 Поддержка", F.chat.type == ChatType.PRIVATE)
async def handle_support_button(message: types.Message):
    support_msg = """
📞 <b>Служба поддержки</b>

По всем вопросам обращайтесь:
👉 WhatsApp: <a href="https://wa.me/77754850900">+7 775 485 09 00</a>
⏰ Часы работы: Пн-Пт, 10:00-22:00
    """
    await message.answer(support_msg, parse_mode="HTML")

@dp.message(F.text == "📢 Рассылка", F.chat.type == ChatType.PRIVATE)
async def start_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("🚫 Доступ запрещен", reply_markup=types.ReplyKeyboardRemove())
    
    cancel_kb = ReplyKeyboardBuilder()
    cancel_kb.button(text="❌ Отменить")
    cancel_kb.adjust(2)
    
    await message.answer(
        "📤 Отправьте сообщение для рассылки (текст, фото или видео):",
        reply_markup=cancel_kb.as_markup(resize_keyboard=True)
    )
    await state.set_state(BroadcastStates.waiting_content)

@dp.message(BroadcastStates.waiting_content)
async def process_content(message: types.Message, state: FSMContext):
    content = {
        'text': message.html_text if message.text else message.caption if message.caption else "",
        'photo': message.photo[-1].file_id if message.photo else None,
        'video': message.video.file_id if message.video else None,
        'document': message.document.file_id if message.document else None
    }
    
    if not any(content.values()):
        return await message.answer("❌ Сообщение не может быть пустым")
    
    await state.update_data(content=content)
    
    confirm_kb = ReplyKeyboardBuilder()
    confirm_kb.button(text="✅ Подтвердить рассылку")
    confirm_kb.button(text="❌ Отменить")
    confirm_kb.adjust(2)

    if message.text == "❌ Отменить":
            await state.clear()
            await show_main_menu(message, "❌ Рассылка отменена")
            return
    
    preview_text = "📋 Предпросмотр рассылки:\n\n" + content['text']
    try:
        if content['photo']:
            await message.answer_photo(content['photo'], caption=preview_text)
        elif content['video']:
            await message.answer_video(content['video'], caption=preview_text)
        elif content['document']:
            await message.answer_document(content['document'], caption=preview_text)
        else:
            await message.answer(preview_text)
    except Exception as e:
        logger.error(f"Ошибка предпросмотра: {e}")
        return await message.answer("❌ Ошибка при создании предпросмотра")
    
    await message.answer(
        "Выберите действие:",
        reply_markup=confirm_kb.as_markup(resize_keyboard=True)
    )
    await state.set_state(BroadcastStates.waiting_confirm)

@dp.message(BroadcastStates.waiting_confirm)
async def confirm_broadcast(message: types.Message, state: FSMContext):
    if message.text == "❌ Отменить":
        await state.clear()
        await show_main_menu(message, "❌ Рассылка отменена")
        return
    
    if message.text == "✅ Подтвердить рассылку":
        await send_broadcast(message, state)
        return
    
    await message.answer("Пожалуйста, используйте кнопки для выбора действия")

async def show_main_menu(message: types.Message, text: str = None):
    main_kb = ReplyKeyboardBuilder()
    main_kb.button(text="📄 Публичная оферта")
    main_kb.button(text="📞 Поддержка")
    main_kb.button(text="👤 Мой профиль")
    
    if message.from_user.id == ADMIN_ID:
        main_kb.button(text="📢 Рассылка")
    
    main_kb.adjust(2)
    
    if text:
        await message.answer(text, reply_markup=main_kb.as_markup(resize_keyboard=True))
    else:
        await message.answer("🏠 Главное меню:", reply_markup=main_kb.as_markup(resize_keyboard=True))

async def send_broadcast(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if 'content' not in data:
        await message.answer("❌ Ошибка: данные рассылки не найдены", reply_markup=types.ReplyKeyboardRemove())
        await state.clear()
        return
 
    users = await get_all_users()
    if not users:
        await message.answer("❌ Нет пользователей для рассылки", reply_markup=types.ReplyKeyboardRemove())
        await state.clear()
        return
   
    progress_msg = await message.answer("🔄 Начинаем рассылку...")
    
    success = 0
    errors = 0
    total_users = len(users)
 
    for index, user_id in enumerate(users, 1):
        try:
            content = data['content']
      
            if content.get('photo'):
                await bot.send_photo(
                    chat_id=user_id,
                    photo=content['photo'],
                    caption=content.get('text', ''),
                    parse_mode='HTML'
                )
            elif content.get('video'):
                await bot.send_video(
                    chat_id=user_id,
                    video=content['video'],
                    caption=content.get('text', ''),
                    parse_mode='HTML'
                )
            elif content.get('document'):
                await bot.send_document(
                    chat_id=user_id,
                    document=content['document'],
                    caption=content.get('text', ''),
                    parse_mode='HTML'
                )
            else:
                await bot.send_message(
                    chat_id=user_id,
                    text=content.get('text', ''),
                    parse_mode='HTML'
                )
            
            success += 1
       
            if index % 10 == 0 or index == total_users:
                progress = int(index / total_users * 100)
                await progress_msg.edit_text(
                    f"🔄 Рассылка в процессе...\n"
                    f"📊 Прогресс: {progress}%\n"
                    f"✅ Успешно: {success}\n"
                    f"❌ Ошибок: {errors}"
                )
                
        except Exception as e:
            errors += 1
            logger.error(f"Ошибка отправки пользователю {user_id}: {str(e)}")
         
            await asyncio.sleep(1)
  
    try:
        await progress_msg.delete()
    except:
        pass
  
    report_message = (
        f"📊 Рассылка завершена!\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"✅ Успешно отправлено: {success}\n"
        f"❌ Ошибок: {errors}\n"
        f"📈 Успешных доставок: {int(success/total_users*100)}%"
    )

    await message.answer(report_message, reply_markup=types.ReplyKeyboardRemove())
    await state.clear()

async def execute_scheduled_broadcast(content: dict):
    users = await get_all_users()
    for user_id in users:
        try:
            if content['photo']:
                await bot.send_photo(user_id, content['photo'], caption=content['text'])
            elif content['video']:
                await bot.send_video(user_id, content['video'], caption=content['text'])
            elif content['document']:
                await bot.send_document(user_id, content['document'], caption=content['text'])
            else:
                await bot.send_message(user_id, content['text'])
        except Exception as e:
            logger.error(f"Scheduled broadcast error: {str(e)}")

@dp.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def ignore_group_messages(message: types.Message):
    pass  

async def delete_bot_commands():
    await bot.delete_my_commands(scope=BotCommandScopeAllPrivateChats())
   
    await bot.delete_my_commands()
    
async def on_startup():
    await create_db_pool()
    await init_db()
    await delete_bot_commands()
    scheduler.start()

async def main():
    await create_db_pool()
    await init_db()
    asyncio.create_task(check_access_periodically())

async def on_shutdown():
    scheduler.shutdown()
    await close_db_pool()
    await bot.session.close()

if __name__ == '__main__':
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    try:
        asyncio.run(dp.start_polling(bot))
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")
