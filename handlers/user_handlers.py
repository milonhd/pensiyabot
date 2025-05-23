# handlers/user_handlers.py
import logging
import time
from aiogram import F, Bot, types, Dispatcher
from aiogram.filters import Command
from aiogram.enums import ChatType
from aiogram.types import FSInputFile
from keyboards import main_keyboard, get_main_menu_keyboard
from database import save_user, get_user_access

logger = logging.getLogger(__name__)

async def show_main_menu(message: types.Message, text: str = None):
    from config import ADMIN_ID # Импортируем здесь
    if text:
        await message.answer(text, reply_markup=get_main_menu_keyboard(ADMIN_ID, message.from_user.id))
    else:
        await message.answer("🏠 Главное меню:", reply_markup=get_main_menu_keyboard(ADMIN_ID, message.from_user.id))

# Декоратор @Command("start") остается, так как он не является Command фильтром
@Command("start")
@F.chat.type == ChatType.PRIVATE
async def cmd_start(message: types.Message):
    await save_user(message.from_user)
    user = message.from_user
    name = user.first_name or "Пользователь"

    from config import ADMIN_ID # Импортируем здесь
    if message.from_user.id == ADMIN_ID:
        await message.answer("Добро пожаловать, Админ! Используйте /help для получения списка команд.",  reply_markup=get_main_menu_keyboard(ADMIN_ID, message.from_user.id))
    else:
        expire_time, _ = await get_user_access(message.from_user.id)
        if expire_time and expire_time > time.time():
            await message.answer(f"👋 Добро пожаловать, {name}! У вас уже есть доступ.", reply_markup=get_main_menu_keyboard(ADMIN_ID, message.from_user.id))
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
            await message.answer(welcome_text, parse_mode="Markdown", reply_markup=get_main_menu_keyboard(ADMIN_ID, message.from_user.id))
            await message.answer(
                "👇 Выберите желаемый уровень:",
                reply_markup=main_keyboard
            )

@F.text == "📄 Публичная оферта"
@F.chat.type == ChatType.PRIVATE
async def handle_offer_button(message: types.Message):
    pdf_path = "oferta.pdf"
    try:
        document = FSInputFile(pdf_path)
        await message.answer_document(document)
    except Exception as e:
        await message.answer("⚠️ Ошибка при отправке файла: " + str(e))

@F.text == "📞 Поддержка"
@F.chat.type == ChatType.PRIVATE
async def handle_support_button(message: types.Message):
    support_msg = """
📞 <b>Служба поддержки</b>

По всем вопросам обращайтесь:
👉 WhatsApp: <a href="https://wa.me/77754850900">+7 775 485 09 00</a>
⏰ Часы работы: Пн-Пт, 10:00-22:00
    """
    await message.answer(support_msg, parse_mode="HTML")

@F.new_chat_members
async def remove_join_message(message: types.Message):
    try:
        await message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить join-сообщение: {e}")

@F.left_chat_member
async def remove_leave_message(message: types.Message):
    try:
        await message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить leave-сообщение: {e}")

@F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP})
async def ignore_group_messages(message: types.Message):
    pass

def register_user_handlers(dp: Dispatcher):
    dp.message.register(cmd_start, Command("start"), F.chat.type == ChatType.PRIVATE)
    dp.message.register(handle_offer_button, F.text == "📄 Публичная оферта", F.chat.type == ChatType.PRIVATE)
    dp.message.register(handle_support_button, F.text == "📞 Поддержка", F.chat.type == ChatType.PRIVATE)
    dp.message.register(remove_join_message, F.new_chat_members)
    dp.message.register(remove_leave_message, F.left_chat_member)
