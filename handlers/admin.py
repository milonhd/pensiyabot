import logging
import time
from aiogram import types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ChatType
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from config import ADMIN_ID, GROUP_IDS
from database.operations import (
    get_user_access, set_user_access, revoke_user_access,
    get_all_active_users, delete_user_access, get_all_users
)


logger = logging.getLogger(__name__)


class BroadcastStates(StatesGroup):
    waiting_content = State()
    waiting_confirm = State()
    waiting_time = State()


async def cmd_help(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("Нет доступа.")
    await message.answer("""
/g [id] [basic/pro/2025-2031] - выдать доступ
/revoke [id] - отозвать доступ
/status [id] - статус доступа
/users - показать всех с доступом
/help - команды
    """)


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
        materials_keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="🏰 Получить материалы", callback_data="get_materials")]
        ])
        await message.bot.send_message(
            user_id,
            f"✅ Доступ к материалам уровня {tariff.upper()} активирован на {duration // 86400} дней!",
            reply_markup=materials_keyboard
        )
    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await message.answer("Произошла ошибка.")


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
            await revoke_user_access(user_id)
            # Уведомление для пользователя
            await message.bot.send_message(user_id, "❌ Ваш доступ был отозван. Теперь вы не можете получать материалы.")

            # Уведомление для администратора
            await message.bot.send_message(ADMIN_ID, f"Доступ пользователя {user_id} был отозван.")

            for group_id in GROUP_IDS:
                try:
                    await message.bot.ban_chat_member(group_id, user_id)
                    await message.bot.unban_chat_member(group_id, user_id)  # чтобы он мог снова вступить позже
                    logging.info(f"Пользователь {user_id} удалён из группы {group_id}")
                except Exception as e:
                    logging.error(f"Не удалось удалить пользователя из группы {group_id}: {e}")
        
        else:
            await message.answer("У пользователя нет доступа.")
    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await message.answer("Произошла ошибка.")


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


async def process_content(message: types.Message, state: FSMContext):
    # Обработка контента
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


async def confirm_broadcast(message: types.Message, state: FSMContext):
    if message.text == "❌ Отменить":
        await state.clear()
        await show_main_menu(message, "❌ Рассылка отменена")
        return
    
    if message.text == "✅ Подтвердить рассылку":
        await send_broadcast(message, state)
        return
    
    await message.answer("Пожалуйста, используйте кнопки для выбора действия")


async def send_broadcast(message: types.Message, state: FSMContext):
    # Получаем данные из состояния
    data = await state.get_data()
    if 'content' not in data:
        await message.answer("❌ Ошибка: данные рассылки не найдены", reply_markup=types.ReplyKeyboardRemove())
        await state.clear()
        return
    
    # Получаем список всех пользователей
    users = await get_all_users()
    if not users:
        await message.answer("❌ Нет пользователей для рассылки", reply_markup=types.ReplyKeyboardRemove())
        await state.clear()
        return
    
    # Отправляем сообщение о начале рассылки
    progress_msg = await message.answer("🔄 Начинаем рассылку...")
    
    success = 0
    errors = 0
    total_users = len(users)
    
    # Отправляем сообщения с прогресс-баром
    for index, user_id in enumerate(users, 1):
        try:
            content = data['content']
            
            # Отправка в зависимости от типа контента
            if content.get('photo'):
                await message.bot.send_photo(
                    chat_id=user_id,
                    photo=content['photo'],
                    caption=content.get('text', ''),
                    parse_mode='HTML'
                )
            elif content.get('video'):
                await message.bot.send_video(
                    chat_id=user_id,
                    video=content['video'],
                    caption=content.get('text', ''),
                    parse_mode='HTML'
                )
            elif content.get('document'):
                await message.bot.send_document(
                    chat_id=user_id,
                    document=content['document'],
                    caption=content.get('text', ''),
                    parse_mode='HTML'
                )
            else:
                await message.bot.send_message(
                    chat_id=user_id,
                    text=content.get('text', ''),
                    parse_mode='HTML'
                )
            
            success += 1
            
            # Обновляем прогресс каждые 10 сообщений или для последнего сообщения
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
            
            # Делаем небольшую паузу при ошибках, чтобы не получить flood control
            await asyncio.sleep(1)
    
    # Удаляем сообщение о прогрессе
    try:
        await progress_msg.delete()
    except:
        pass
    
    # Отправляем финальный отчет
    report_message = (
        f"📊 Рассылка завершена!\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"✅ Успешно отправлено: {success}\n"
        f"❌ Ошибок: {errors}\n"
        f"📈 Успешных доставок: {int(success/total_users*100)}%"
    )

    await message.answer(report_message, reply_markup=types.ReplyKeyboardRemove())
    await state.clear()


async def show_main_menu(message: types.Message, text: str = None):
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


async def approve_user(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Недостаточно прав")

    user_id = int(call.data.split("_")[1])
    _, tariff = await get_user_access(user_id)

    # Проверка наличия чека
    pool = await create_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT 1 FROM fiscal_checks WHERE user_id = %s", (user_id,))
            if not await cur.fetchone():
                return await call.answer("❌ У пользователя нет подтвержденного чека")

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
    materials_keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🏰 Получить материалы", callback_data="get_materials")]
    ])
    await call.bot.send_message(
        user_id, 
        f"✅ Доступ уровня {tariff.upper()} выдан на {duration // 86400} дней!", 
        reply_markup=materials_keyboard
    )

    # Убираем кнопку
    await call.message.edit_reply_markup(reply_markup=None)
    await call.answer("Доступ выдан.")


def register_admin_handlers(dp):
    dp.message.register(cmd_help, Command("help"), F.chat.type == ChatType.PRIVATE)
    dp.message.register(grant_access, Command("g"), F.chat.type == ChatType.PRIVATE)
    dp.message.register(revoke_access, Command("revoke"), F.chat.type == ChatType.PRIVATE)
    dp.message.register(check_status, Command("status"), F.chat.type == ChatType.PRIVATE)
    dp.message.register(show_users, Command("users"), F.chat.type == ChatType.PRIVATE)
    dp.message.register(start_broadcast, F.text == "📢 Рассылка", F.chat.type == ChatType.PRIVATE)
    dp.message.register(process_content, BroadcastStates.waiting_content)
    dp.message.register(confirm_broadcast, BroadcastStates.waiting_confirm)
    dp.callback_query.register(approve_user, lambda c: c.data.startswith("approve_"))
