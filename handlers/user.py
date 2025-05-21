import logging
import time
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.enums import ChatType
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from config import ADMIN_ID, GROUP_IDS, bot
from database.operations import (
    get_user_access, set_user_access, save_user,
    get_all_active_users, get_all_users
)
from utils.keyboards import (
    main_keyboard, materials_keyboard,
    get_self_years_keyboard, get_year_buttons
)

# Настройка логгера
logger = logging.getLogger(__name__)

# Инициализация роутера
router = Router()

@router.message(Command("start"), F.chat.type == ChatType.PRIVATE)
async def cmd_start(message: types.Message):
    """Обработка команды /start"""
    await save_user(message.from_user)
    user = message.from_user
    name = user.first_name or "Пользователь"

    # Создаем основную клавиатуру
    main_kb = ReplyKeyboardBuilder()
    main_kb.button(text="📄 Публичная оферта")
    main_kb.button(text="📞 Поддержка")
    
    if message.from_user.id == ADMIN_ID:
        main_kb.button(text="📢 Рассылка")
    
    main_kb.adjust(2)  # 2 кнопки в ряд
    
    if message.from_user.id == ADMIN_ID:
        await message.answer(
            "Добро пожаловать, Админ! Используйте /help для получения списка команд.",
            reply_markup=main_kb.as_markup(resize_keyboard=True, one_time_keyboard=False)
        )
    else:
        expire_time, _ = await get_user_access(message.from_user.id)
        if expire_time and expire_time > time.time():
            await message.answer(
                f"👋 Добро пожаловать, {name}! У вас уже есть доступ.", 
                reply_markup=main_kb.as_markup(resize_keyboard=True, one_time_keyboard=False)
            )
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
            await message.answer(
                welcome_text, 
                parse_mode="Markdown", 
                reply_markup=main_kb.as_markup(resize_keyboard=True, one_time_keyboard=False)
            )
            await message.answer(
                "👇 Выберите желаемый уровень:",
                reply_markup=main_keyboard  # это InlineKeyboardMarkup
            )

@router.message(F.text == "📄 Публичная оферта", F.chat.type == ChatType.PRIVATE)
async def handle_offer_button(message: types.Message):
    """Обработка кнопки Публичная оферта"""
    pdf_path = "oferta.pdf"
    try:
        document = FSInputFile(pdf_path)
        await message.answer_document(document)
    except Exception as e:
        await message.answer("⚠️ Ошибка при отправке файла: " + str(e))

@router.message(F.text == "📞 Поддержка", F.chat.type == ChatType.PRIVATE)
async def handle_support_button(message: types.Message):
    """Обработка кнопки Поддержка"""
    support_msg = """
📞 <b>Служба поддержки</b>

По всем вопросам обращайтесь:
👉 WhatsApp: <a href="https://wa.me/77754850900">+7 775 485 09 00</a>
⏰ Часы работы: Пн-Пт, 10:00-22:00
    """
    await message.answer(support_msg, parse_mode="HTML")

@router.callback_query(lambda c: c.data == "get_materials")
async def handle_get_materials(call: types.CallbackQuery):
    """Обработка кнопки Получить материалы"""
    # Деактивируем кнопку сразу после нажатия
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
    
    user_id = call.from_user.id
    expire_time, tariff = await get_user_access(user_id)
    
    if not expire_time or expire_time < time.time():
        return await call.message.answer("❌ У вас нет активного доступа.")

    # Сопоставление тарифов и ID групп
    tariff_chat_map = {
        "basic": GROUP_IDS[0],
        "2025": GROUP_IDS[1],
        "2026": GROUP_IDS[2],
        "2027": GROUP_IDS[3],
        "2028": GROUP_IDS[4], 
        "2029": GROUP_IDS[5],
        "2030": GROUP_IDS[6],
        "2031": GROUP_IDS[7]
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
            f"🔐 Ваша персональная ссылка (исчезнет спустя 15 секунд):\n{invite.invite_link}"
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

# Обработчик для неактивной кнопки
@router.callback_query(F.data == "used_link")
async def handle_used_link(call: types.CallbackQuery):
    await call.answer("Вы уже использовали эту ссылку", show_alert=True)

@router.callback_query(lambda c: c.data.startswith("year_"))
async def handle_year_selection(call: types.CallbackQuery):
    """Обработчик выбора года для уровня САМОСТОЯТЕЛЬНЫЙ"""
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

@router.callback_query(F.data == "self")
async def handle_self_level(call: types.CallbackQuery):
    """Обработчик выбора уровня САМОСТОЯТЕЛЬНЫЙ"""
    await call.message.answer("📅 Выберите год вашего выхода на пенсию:", 
                            reply_markup=get_self_years_keyboard())

@router.callback_query(F.data == "basic")
async def handle_basic_level(call: types.CallbackQuery):
    """Обработчик выбора уровня БАЗОВЫЙ"""
    user_id = call.from_user.id
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

@router.callback_query(F.data == "pro")
async def handle_pro_level(call: types.CallbackQuery):
    """Обработчик выбора уровня ПРО"""
    user_id = call.from_user.id
    await set_user_access(user_id, None, "pro")  # Временно сохраняем выбор
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Оплатить", url="https://pay.kaspi.kz/pay/vx2s6z0c")],
        [InlineKeyboardButton(text="📄 Отправить чек", callback_data="send_screenshot_pro")]
    ])
    await call.message.answer("❌ Временно недоступно", reply_markup=keyboard)

@router.callback_query(F.data.startswith("send_screenshot_"))
async def handle_screenshot_request(call: types.CallbackQuery):
    """Обработчик нажатия на кнопку Отправить чек"""
    user_id = call.from_user.id
    expire_time, current_tariff = await get_user_access(user_id)
    
    # Проверяем есть ли активный доступ
    if expire_time and expire_time > time.time():
        await call.answer("❗ У вас уже есть активный доступ!", show_alert=True)
        return
    
    year_or_tariff = call.data.split("_")[2]
    await set_user_access(user_id, None, year_or_tariff)
    await call.message.answer(
        f"📄 Пожалуйста, отправьте PDF-файл фискального чека из Kaspi!\n\n"
        "📌 Как получить чек:\n"
        "1. После оплаты в Kaspi нажмите «Показать чек об оплате»\n"
        "2. Нажмите «Поделиться»\n"
        "3. Отправьте чек в этот чат\n\n"
    )

@router.message(F.new_chat_members)
async def remove_join_message(message: types.Message):
    """Удаление сообщений о входе новых участников"""
    try:
        await message.delete()
    except Exception as e:
        logging.warning(f"Не удалось удалить join-сообщение: {e}")

@router.message(F.left_chat_member)
async def remove_leave_message(message: types.Message):
    """Удаление сообщений о выходе участников"""
    try:
        await message.delete()
    except Exception as e:
        logging.warning(f"Не удалось удалить leave-сообщение: {e}")

async def show_main_menu(message: types.Message, text: str = None):
    """Показ главного меню"""
    main_kb = ReplyKeyboardBuilder()
    main_kb.button(text="📄 Публичная оферта")
    main_kb.button(text="📞 Поддержка")
    
    if message.from_user.id == ADMIN_ID:
        main_kb.button(text="📢 Рассылка")
    
    main_kb.adjust(2)
    
    if text:
        await message.answer(text, reply_markup=main_kb.as_markup(resize_keyboard=True))
    else:
        await message.answer("🏠 Главное меню:", reply_markup=main_kb.as_markup(resize_keyboard=True))
