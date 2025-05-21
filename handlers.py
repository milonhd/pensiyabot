import logging
import os
from typing import List
from aiogram import Bot, Dispatcher, types, filters
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ChatType
from database import Database
import keyboards
from constants import TARIFF_DURATIONS, REQUIRED_AMOUNTS, GROUP_IDS, TARIFF_CHAT_MAP
from datetime import datetime
import time
import asyncio

logger = logging.getLogger(__name__)

class BroadcastStates(StatesGroup):
    waiting_content = State()
    waiting_confirm = State()

class UserHandlers:
    def __init__(self, db: Database, bot: Bot, admin_id: int, group_ids: List[int], receipt_dir: str):
        self.db = db
        self.bot = bot
        self.admin_id = admin_id
        self.group_ids = group_ids
        self.receipt_dir = receipt_dir

    async def cmd_start(self, message: types.Message):
        """Обработчик команды /start."""
        await self.db.save_user(message.from_user.id, message.from_user.username, 
                              message.from_user.first_name, message.from_user.last_name)
        name = message.from_user.first_name or "Пользователь"
        
        main_kb = keyboards.get_main_keyboard(message.from_user.id == self.admin_id)
        
        expire_time, _ = await self.db.get_user_access(message.from_user.id)
        if expire_time and expire_time > time.time():
            await message.answer(f"👋 Добро пожаловать, {name}! У вас уже есть доступ.", 
                               reply_markup=main_kb.as_markup(resize_keyboard=True))
        else:
            welcome_text = (
                f"👋 *Добро пожаловать, {name}, в бот «СВОЯ ПЕНСИЯ»* – твой персональный помощник на пути к достойной пенсии!\n"
                "Здесь ты найдёшь всё, чтобы понимать на какую пенсию ты можешь рассчитывать, как её увеличить и какие выплаты тебе положены именно в твоей ситуации.\n\n"
                "👉 *Внутри уже доступно:*\n"
                "1️⃣ Разборы пенсий в Казахстане: кто, когда и сколько может получить\n"
                "2️⃣ Доступ к закрытым материалам: текст, видео, фото — в зависимости от выбранного тарифа\n\n"
                "💰 *Уровни:*\n"
                "*САМОСТОЯТЕЛЬНЫЙ* — 10 000 тг\n"
                "*БАЗОВЫЙ* — 50 000 тг\n"
                "*ПРО* — 250 000 тг\n\n"
                "Ты можешь оплатить прямо здесь и отправить чек оплаты. После этого администратор активирует тебе доступ.\n\n"
                "Ты не один — давай разбираться вместе!\n"
            )
            await message.answer(welcome_text, parse_mode="Markdown", 
                               reply_markup=main_kb.as_markup(resize_keyboard=True))
            await message.answer("👇 Выберите желаемый уровень:", reply_markup=keyboards.main_keyboard)

    async def handle_offer_button(self, message: types.Message):
        """Обработчик кнопки 'Публичная оферта'."""
        pdf_path = "oferta.pdf"
        try:
            document = types.FSInputFile(pdf_path)
            await message.answer_document(document)
        except Exception as e:
            await message.answer(f"⚠️ Ошибка при отправке файла: {e}")
            logger.error(f"Ошибка отправки оферты: {e}")

    async def handle_support_button(self, message: types.Message):
        """Обработчик кнопки 'Поддержка'."""
        support_msg = """
📞 <b>Служба поддержки</b>
По всем вопросам обращайтесь:
👉 WhatsApp: <a href="https://wa.me/77754850900">+7 775 485 09 00</a>
⏰ Часы работы: Пн-Пт, 10:00-22:00
        """
        await message.answer(support_msg, parse_mode="HTML")

    async def handle_document(self, message: types.Message):
        """Обработчик отправки PDF-документа (чека)."""
        user = message.from_user
        if message.document.mime_type != 'application/pdf':
            return await message.answer("❌ Пожалуйста, отправьте PDF-файл чека из Kaspi")

        file_id = message.document.file_id
        if await self.db.check_duplicate_file(file_id):
            return await message.answer("❌ Этот чек уже был загружен ранее")

        os.makedirs(self.receipt_dir, exist_ok=True)
        file_path = os.path.join(self.receipt_dir, f"{user.id}_{message.document.file_name}")
        await self.bot.download(file=await self.bot.get_file(file_id), destination=file_path)

        receipt_data = await self.db.parse_kaspi_receipt(file_path)
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
            f"Данные чека:\n"
            f"ИИН: {receipt_data['iin']}\n"
            f"Сумма: {receipt_data['amount']}\n"
            f"Номер чека: {receipt_data['check_number']}\n"
            f"Дата: {receipt_data['date_time']}"
        )

        expire_time, tariff = await self.db.get_user_access(user.id)
        errors = []
        if receipt_data["iin"] != "620613400018":
            errors.append("ИИН продавца не совпадает")
        if receipt_data["amount"] != REQUIRED_AMOUNTS.get(tariff, 0):
            errors.append(f"Сумма не соответствует тарифу {tariff}")

        if errors:
            return await message.answer("❌ Ошибки в чеке:\n" + "\n".join(errors))

        if not await self.db.save_receipt(
            user_id=user.id,
            amount=receipt_data["amount"],
            check_number=receipt_data["check_number"],
            fp=receipt_data["fp"],
            date_time=date_time,
            buyer_name=receipt_data["buyer_name"],
            file_id=file_id
        ):
            return await message.answer("❌ Ошибка при сохранении чека")

        duration = TARIFF_DURATIONS.get(tariff, 7) * 86400
        await self.db.set_user_access(user.id, time.time() + duration, tariff)
        await message.answer(
            f"✅ Доступ уровня {tariff.upper()} активирован на {duration//86400} дней!",
            reply_markup=keyboards.materials_keyboard
        )

        info = (
            f"📄 Фискальный чек от пользователя:\n"
            f"🆔 ID: {user.id}\n"
            f"👤 Username: @{user.username or 'Без username'}\n"
            f"💳 Уровень: {tariff.upper() if tariff else 'не выбран'}\n"
            f"📝 Файл: {message.document.file_name}"
        )
        await self.bot.send_message(self.admin_id, info)
        await self.bot.send_document(self.admin_id, file_id)

class AdminHandlers:
    def __init__(self, db: Database, bot: Bot, admin_id: int, group_ids: List[int]):
        self.db = db
        self.bot = bot
        self.admin_id = admin_id
        self.group_ids = group_ids

    async def cmd_grant(self, message: types.Message):
        """Обработчик команды /g для выдачи доступа."""
        if message.from_user.id != self.admin_id:
            return await message.answer("Нет доступа.")
        args = message.text.split()
        if len(args) < 3:
            return await message.answer("Использование: /g [id] [basic/pro/2025-2031]")
        try:
            user_id = int(args[1])
            tariff = args[2].lower()
            if tariff not in ["basic", "pro"] + [str(y) for y in range(2025, 2032)]:
                return await message.answer("Тариф должен быть 'basic', 'pro' или '2025'-'2031'.")

            duration = TARIFF_DURATIONS.get(tariff, 7) * 86400
            expire_time = time.time() + duration
            await self.db.set_user_access(user_id, expire_time, tariff)

            await message.answer(f"Доступ выдан пользователю {user_id} ({tariff}) на {duration // 86400} дней.")
            await self.bot.send_message(
                user_id,
                f"✅ Доступ к материалам уровня {tariff.upper()} активирован на {duration // 86400} дней!",
                reply_markup=keyboards.materials_keyboard
            )
        except Exception as e:
            logger.error(f"Ошибка выдачи доступа: {e}", exc_info=True)
            await message.answer("Произошла ошибка.")

    async def cmd_revoke(self, message: types.Message):
        """Обработчик команды /revoke для отзыва доступа."""
        if message.from_user.id != self.admin_id:
            return await message.answer("Нет доступа.")
        args = message.text.split()
        if len(args) < 2:
            return await message.answer("Укажите ID пользователя.")

        try:
            user_id = int(args[1])
            expire_time, _ = await self.db.get_user_access(user_id)
            if expire_time:
                await self.db.revoke_user_access(user_id)
                await self.bot.send_message(user_id, "❌ Ваш доступ был отозван.")
                await self.bot.send_message(self.admin_id, f"Доступ пользователя {user_id} был отозван.")

                for group_id in self.group_ids:
                    try:
                        await self.bot.ban_chat_member(group_id, user_id)
                        await self.bot.unban_chat_member(group_id, user_id)
                        logger.info(f"Пользователь {user_id} удалён из группы {group_id}")
                    except Exception as e:
                        logger.error(f"Не удалось удалить пользователя из группы {group_id}: {e}")
            else:
                await message.answer("У пользователя нет доступа.")
        except Exception as e:
            logger.error(f"Ошибка отзыва доступа: {e}", exc_info=True)
            await message.answer("Произошла ошибка.")

    async def cmd_status(self, message: types.Message):
        """Обработчик команды /status для проверки статуса доступа."""
        if message.from_user.id != self.admin_id:
            return await message.answer("Нет доступа.")
        args = message.text.split()
        if len(args) < 2:
            return await message.answer("Укажите ID пользователя.")

        try:
            user_id = int(args[1])
            expire_time, tariff = await self.db.get_user_access(user_id)
            if expire_time and expire_time > time.time():
                remaining_seconds = expire_time - time.time()
                days = int(remaining_seconds // (24 * 60 * 60))
                await message.answer(
                    f"✅ У пользователя {user_id} есть доступ ({tariff.upper()}). Осталось дней: {days}."
                )
            else:
                await message.answer("❌ Доступа нет или он истек.")
        except Exception as e:
            logger.error(f"Ошибка проверки статуса: {e}", exc_info=True)
            await message.answer("Ошибка при проверки статуса.")

    async def cmd_users(self, message: types.Message):
        """Обработчик команды /users для показа активных пользователей."""
        if message.from_user.id != self.admin_id:
            return await message.answer("Нет доступа.")
        active_users = await self.db.get_all_active_users()
        if not active_users:
            return await message.answer("Пока нет пользователей с доступом.")
        
        lines = [
            f"{uid} - до {time.ctime(exp)} ({tariff})"
            for uid, exp, tariff in active_users
        ]
        await message.answer("\n".join(lines))

    async def cmd_help(self, message: types.Message):
        """Обработчик команды /help для админа."""
        if message.from_user.id != self.admin_id:
            return await message.answer("Нет доступа.")
        await message.answer("""
/g [id] [basic/pro/2025-2031] - выдать доступ
/revoke [id] - отозвать доступ
/status [id] - статус доступа
/users - показать всех с доступом
/help - команды
        """)

    async def handle_broadcast_start(self, message: types.Message, state: FSMContext):
        """Обработчик начала рассылки."""
        if message.from_user.id != self.admin_id:
            return await message.answer("🚫 Доступ запрещен", reply_markup=types.ReplyKeyboardRemove())
        
        cancel_kb = keyboards.ReplyKeyboardBuilder()
        cancel_kb.button(text="❌ Отменить")
        cancel_kb.adjust(2)
        
        await message.answer(
            "📤 Отправьте сообщение для рассылки (текст, фото или видео):",
            reply_markup=cancel_kb.as_markup(resize_keyboard=True)
        )
        await state.set_state(BroadcastStates.waiting_content)

    async def handle_broadcast_content(self, message: types.Message, state: FSMContext):
        """Обработчик контента рассылки."""
        content = {
            'text': message.html_text if message.text else message.caption if message.caption else "",
            'photo': message.photo[-1].file_id if message.photo else None,
            'video': message.video.file_id if message.video else None,
            'document': message.document.file_id if message.document else None
        }
        
        if not any(content.values()):
            return await message.answer("❌ Сообщение не может быть пустым")
        
        await state.update_data(content=content)
        
        confirm_kb = keyboards.ReplyKeyboardBuilder()
        confirm_kb.button(text="✅ Подтвердить рассылку")
        confirm_kb.button(text="❌ Отменить")
        confirm_kb.adjust(2)

        if message.text == "❌ Отменить":
            await state.clear()
            await self.show_main_menu(message, "❌ Рассылка отменена")
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
            logger.error(f"Ошибка предпросмотра: {e}", exc_info=True)
            return await message.answer("❌ Ошибка при создании предпросмотра")
        
        await message.answer(
            "Выберите действие:",
            reply_markup=confirm_kb.as_markup(resize_keyboard=True)
        )
        await state.set_state(BroadcastStates.waiting_confirm)

    async def handle_broadcast_confirm(self, message: types.Message, state: FSMContext):
        """Обработчик подтверждения рассылки."""
        if message.text == "❌ Отменить":
            await state.clear()
            await self.show_main_menu(message, "❌ Рассылка отменена")
            return
        
        if message.text == "✅ Подтвердить рассылку":
            await self.send_broadcast(message, state)
            return
        
        await message.answer("Пожалуйста, используйте кнопки для выбора действия")

    async def show_main_menu(self, message: types.Message, text: str = None):
        """Отображение главного меню."""
        main_kb = keyboards.get_main_keyboard(message.from_user.id == self.admin_id)
        
        if text:
            await message.answer(text, reply_markup=main_kb.as_markup(resize_keyboard=True))
        else:
            await message.answer("🏠 Главное меню:", reply_markup=main_kb.as_markup(resize_keyboard=True))

    async def send_broadcast(self, message: types.Message, state: FSMContext):
        """Отправка рассылки всем пользователям."""
        data = await state.get_data()
        if 'content' not in data:
            await message.answer("❌ Ошибка: данные рассылки не найдены", reply_markup=types.ReplyKeyboardRemove())
            await state.clear()
            return
        
        users = await self.db.get_all_users()
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
                    await self.bot.send_photo(
                        chat_id=user_id,
                        photo=content['photo'],
                        caption=content.get('text', ''),
                        parse_mode='HTML'
                    )
                elif content.get('video'):
                    await self.bot.send_video(
                        chat_id=user_id,
                        video=content['video'],
                        caption=content.get('text', ''),
                        parse_mode='HTML'
                    )
                elif content.get('document'):
                    await self.bot.send_document(
                        chat_id=user_id,
                        document=content['document'],
                        caption=content.get('text', ''),
                        parse_mode='HTML'
                    )
                else:
                    await self.bot.send_message(
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
                logger.error(f"Ошибка отправки пользователю {user_id}: {e}")
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

class CallbackHandlers:
    def __init__(self, db: Database, bot: Bot, admin_id: int, group_ids: List[int]):
        self.db = db
        self.bot = bot
        self.admin_id = admin_id
        self.group_ids = group_ids

    async def handle_callback(self, call: types.CallbackQuery):
        """Обработчик callback-запросов."""
        if call.message.chat.type != ChatType.PRIVATE:
            return

        data = call.data
        user_id = call.from_user.id

        if data == "self":
            await call.message.answer("📅 Выберите год вашего выхода на пенсию:", reply_markup=keyboards.get_self_years_keyboard())
            return

        if data == "basic":
            await self.db.set_user_access(user_id, None, "basic")
            keyboard = keyboards.InlineKeyboardMarkup(inline_keyboard=[
                [keyboards.InlineKeyboardButton(text="✅ Оплатить", url="https://pay.kaspi.kz/pay/vx2s6z0c")],
                [keyboards.InlineKeyboardButton(text="📄 Отправить чек", callback_data="send_screenshot_basic")]
            ])
            await call.message.answer(
                """
🔸 Уровень БАЗОВЫЙ — мини-курс для тех, кто хочет понимать расчёт пенсии и помогать другим

📚 Вы получите:
✔️ Готовый алгоритм расчёта пенсии — пошагово, без сложных формул
✔️ Примеры и шаблоны — как считать, где брать данные
✔️ Видео + текстовые материалы — всё по делу
✔️ Ответы на вопросы по расчёту

🧠 Подходит тем, кто:
– хочет разбираться в теме для себя и близких
– планирует помогать другим
– не хочет тратить время на самостоятельное изучение

⏰ Доступ: 30 дней
💬 Поддержка: вопрос-ответ в общем чате
💳 Стоимость: 50 000 ₸

👇 Нажмите «✅ Оплатить», чтобы перейти к реквизитам.
                """,
                reply_markup=keyboard
            )

        elif data == "pro":
            await self.db.set_user_access(user_id, None, "pro")
            keyboard = keyboards.InlineKeyboardMarkup(inline_keyboard=[
                [keyboards.InlineKeyboardButton(text="✅ Оплатить", url="https://pay.kaspi.kz/pay/vx2s6z0c")],
                [keyboards.InlineKeyboardButton(text="📄 Отправить чек", callback_data="send_screenshot_pro")]
            ])
            await call.message.answer("❌ Временно недоступно", reply_markup=keyboard)

        elif data.startswith("year_"):
            year = data.split("_")[1]
            text = """
🔹 Уровень САМОСТОЯТЕЛЬНЫЙ — чтобы увидеть свою будущую пенсию без сложных расчётов

📌 Подходит, если:
– не дружите с формулами, Excel, не понимаете алгоритм расчета
– просто хотите понять, почему у вас будет такая пенсия
– хотите узнать, что влияет на размер пенсии

📚 Вы получите:
✔️ Готовые материалы в понятной форме — таблицы и видео
✔️ Объяснение на примерах
✔️ Инструкции: что проверить, где взять данные
✔️ Конечный продукт с расчетом вашей пенсии

⏰ Доступ: 7 дней
💬 Вопросы — в общем чате
💳 Стоимость: 10 000 ₸

👇 Нажмите «✅ Оплатить», чтобы перейти к реквизитам.
            """
            await call.message.answer(text, reply_markup=keyboards.get_year_buttons(year))

        elif data.startswith("send_screenshot_"):
            expire_time, current_tariff = await self.db.get_user_access(user_id)
            if expire_time and expire_time > time.time():
                await call.answer("❗ У вас уже есть активный доступ!", show_alert=True)
                return
            year = data.split("_")[2]
            await self.db.set_user_access(user_id, None, year)
            await call.message.answer(
                f"📄 Пожалуйста, отправьте PDF-файл фискального чека из Kaspi!\n\n"
                "📌 Как получить чек:\n"
                "1. После оплаты в Kaspi нажмите «Показать чек об оплате»\n"
                "2. Нажмите «Поделиться»\n"
                "3. Отправьте чек в этот чат\n\n"
            )

        elif data == "get_materials":
            await call.answer()
            await call.message.edit_reply_markup(
                reply_markup=keyboards.InlineKeyboardMarkup(
                    inline_keyboard=[
                        [keyboards.InlineKeyboardButton(
                            text="✅ Материалы получены", 
                            callback_data="used_link"
                        )]
                    ]
                )
            )
            expire_time, tariff = await self.db.get_user_access(user_id)
            if not expire_time or expire_time < time.time():
                return await call.message.answer("❌ У вас нет активного доступа.")

            chat_id = TARIFF_CHAT_MAP.get(tariff)
            if not chat_id:
                return await call.message.answer("❌ Не удалось определить канал по вашему тарифу.")

            try:
                invite = await self.bot.create_chat_invite_link(
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

        elif data == "used_link":
            await call.answer("Вы уже использовали эту ссылку", show_alert=True)

def register_handlers(dp: Dispatcher, db: Database, bot: Bot, admin_id: int, group_ids: List[int]):
    """Регистрация всех обработчиков."""
    user_handlers = UserHandlers(db, bot, admin_id, group_ids, os.getenv("RECEIPT_DIR", "/app/receipts"))
    admin_handlers = AdminHandlers(db, bot, admin_id, group_ids)
    callback_handlers = CallbackHandlers(db, bot, admin_id, group_ids)

    dp.message.register(user_handlers.cmd_start, Command("start"), filters.ChatType.PRIVATE)
    dp.message.register(user_handlers.handle_offer_button, filters.Text(text="📄 Публичная оферта"), filters.ChatType.PRIVATE)
    dp.message.register(user_handlers.handle_support_button, filters.Text(text="📞 Поддержка"), filters.ChatType.PRIVATE)
    dp.message.register(user_handlers.handle_document, lambda m: m.document and m.chat.type == ChatType.PRIVATE)
    dp.message.register(admin_handlers.handle_broadcast_start, filters.Text(text="📢 Рассылка"), filters.ChatType.PRIVATE)
    dp.message.register(admin_handlers.handle_broadcast_content, BroadcastStates.waiting_content)
    dp.message.register(admin_handlers.handle_broadcast_confirm, BroadcastStates.waiting_confirm)
    
    dp.message.register(admin_handlers.cmd_grant, Command("g"), filters.ChatType.PRIVATE)
    dp.message.register(admin_handlers.cmd_revoke, Command("revoke"), filters.ChatType.PRIVATE)
    dp.message.register(admin_handlers.cmd_status, Command("status"), filters.ChatType.PRIVATE)
    dp.message.register(admin_handlers.cmd_users, Command("users"), filters.ChatType.PRIVATE)
    dp.message.register(admin_handlers.cmd_help, Command("help"), filters.ChatType.PRIVATE)
    
    dp.callback_query.register(callback_handlers.handle_callback, lambda c: c.data in ["self", "basic", "pro", "get_materials", "used_link"] or c.data.startswith("year_") or c.data.startswith("send_screenshot_"))
