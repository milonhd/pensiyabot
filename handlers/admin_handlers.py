# handlers/admin_handlers.py
import logging
import time
import asyncio
from aiogram import F, Bot, types, Dispatcher
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.enums import ChatType
from keyboards import get_main_menu_keyboard, get_cancel_keyboard, get_confirm_broadcast_keyboard
from database import get_user_access, set_user_access, revoke_user_access, get_all_active_users, get_all_users
from config import ADMIN_ID

logger = logging.getLogger(__name__)

class BroadcastStates(StatesGroup):
    waiting_content = State()
    waiting_confirm = State()

# Удален декоратор @Command("g")
@F.chat.type == ChatType.PRIVATE
async def grant_access(message: types.Message, bot: Bot):
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
        else: # self
            duration = 7 * 24 * 60 * 60

        expire_time = time.time() + duration
        await set_user_access(user_id, expire_time, tariff)

        await message.answer(f"Доступ выдан пользователю {user_id} ({tariff}) на {duration // 86400} дней.")
        # Предполагается, что `materials_keyboard` импортируется из `keyboards`
        from keyboards import materials_keyboard
        await bot.send_message(
            user_id,
            f"✅ Доступ к материалам уровня {tariff.upper()} активирован на {duration // 86400} дней!",
            reply_markup=materials_keyboard
        )
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await message.answer("Произошла ошибка.")

# Удален декоратор @Command("revoke")
@F.chat.type == ChatType.PRIVATE
async def revoke_access(message: types.Message, bot: Bot):
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
            await bot.send_message(user_id, "❌ Ваш доступ был отозван. Теперь вы не можете получать материалы.")
            await bot.send_message(ADMIN_ID, f"Доступ пользователя {user_id} был отозван.")

            from config import GROUP_IDS # Импортируем здесь, чтобы избежать циклического импорта
            for group_id in GROUP_IDS:
                try:
                    await bot.ban_chat_member(group_id, user_id)
                    await bot.unban_chat_member(group_id, user_id) # чтобы он мог снова вступить позже
                    logger.info(f"Пользователь {user_id} удалён из группы {group_id}")
                except Exception as e:
                    logger.error(f"Не удалось удалить пользователя из группы {group_id}: {e}")
        else:
            await message.answer("У пользователя нет доступа.")
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await message.answer("Произошла ошибка.")

# Удален декоратор @Command("status")
@F.chat.type == ChatType.PRIVATE
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
        logger.error(f"Ошибка: {e}")
        await message.answer("Ошибка при проверке статуса.")

# Удален декоратор @Command("help")
@F.chat.type == ChatType.PRIVATE
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

# Удален декоратор @Command("users")
@F.chat.type == ChatType.PRIVATE
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

# Декоратор F.text == "📢 Рассылка" остается, так как он не является Command фильтром
@F.text == "📢 Рассылка"
@F.chat.type == ChatType.PRIVATE
async def start_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("🚫 Доступ запрещен", reply_markup=types.ReplyKeyboardRemove())

    await message.answer(
        "📤 Отправьте сообщение для рассылки (текст, фото или видео):",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(BroadcastStates.waiting_content)

@BroadcastStates.waiting_content
async def process_content(message: types.Message, state: FSMContext):
    if message.text == "❌ Отменить":
        await state.clear()
        from handlers.user_handlers import show_main_menu # Импортируем здесь
        await show_main_menu(message, "❌ Рассылка отменена")
        return

    content = {
        'text': message.html_text if message.text else message.caption if message.caption else "",
        'photo': message.photo[-1].file_id if message.photo else None,
        'video': message.video.file_id if message.video else None,
        'document': message.document.file_id if message.document else None
    }

    if not any(content.values()):
        return await message.answer("❌ Сообщение не может быть пустым")

    await state.update_data(content=content)

    preview_text = "📋 Предпросмотр рассылки:\n\n" + content['text']
    try:
        if content['photo']:
            await message.answer_photo(content['photo'], caption=preview_text)
        elif content['video']:
            await message.video(content['video'], caption=preview_text)
        elif content['document']:
            await message.answer_document(content['document'], caption=preview_text)
        else:
            await message.answer(preview_text)
    except Exception as e:
        logger.error(f"Ошибка предпросмотра: {e}")
        return await message.answer("❌ Ошибка при создании предпросмотра")

    await message.answer(
        "Выберите действие:",
        reply_markup=get_confirm_broadcast_keyboard()
    )
    await state.set_state(BroadcastStates.waiting_confirm)

@BroadcastStates.waiting_confirm
async def confirm_broadcast(message: types.Message, state: FSMContext, bot: Bot):
    if message.text == "❌ Отменить":
        await state.clear()
        from handlers.user_handlers import show_main_menu # Импортируем здесь
        await show_main_menu(message, "❌ Рассылка отменена")
        return

    if message.text == "✅ Подтвердить рассылку":
        await send_broadcast(message, state, bot)
        return

    await message.answer("Пожалуйста, используйте кнопки для выбора действия")

async def send_broadcast(message: types.Message, state: FSMContext, bot: Bot):
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


def register_admin_handlers(dp: Dispatcher):
    dp.message.register(grant_access, Command("g"))
    dp.message.register(revoke_access, Command("revoke"))
    dp.message.register(check_status, Command("status"))
    dp.message.register(help_admin, Command("help"))
    dp.message.register(show_users, Command("users"))
    dp.message.register(start_broadcast, F.text == "📢 Рассылка")
    dp.message.register(process_content, BroadcastStates.waiting_content)
    dp.message.register(confirm_broadcast, BroadcastStates.waiting_confirm)
