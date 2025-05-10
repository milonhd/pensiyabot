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
    [InlineKeyboardButton(text="Базовый тариф", callback_data="basic")],
    [InlineKeyboardButton(text="Тариф ПРО", callback_data="pro")],
    [InlineKeyboardButton(text="Публичная оферта", callback_data="offer")]
])

materials_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🏰 Получить материалы", callback_data="get_materials")]
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

                "💰 *Тарифы:*\n"
                "*Базовый тариф* — 10 000 тг\n"
                "*Тариф ПРО* — 250 000 тг\n\n"

                "Ты можешь оплатить прямо здесь и отправить скриншот оплаты. После этого администратор активирует тебе доступ, и появится кнопка *ПОЛУЧИТЬ МАТЕРИАЛЫ*.\n\n"

                "Ты не один — давай разбираться вместе!\n"
                "Нажимай *БАЗОВЫЙ ТАРИФ* или *ТАРИФ ПРО*, чтобы начать."
            )
            await message.answer(welcome_text, parse_mode="Markdown", reply_markup=main_keyboard)


@dp.message(Command("grant"))
async def grant_access(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("Нет доступа.")
    args = message.text.split()
    if len(args) < 3:
        return await message.answer("Использование: /grant [id] [basic/pro]")
    try:
        user_id = int(args[1])
        tariff = args[2].lower()
        if tariff not in ["basic", "pro"]:
            return await message.answer("Тариф должен быть 'basic' или 'pro'.")

        days = 7 if tariff == "basic" else 30
        user_access[user_id] = time.time() + 60
        user_tariffs[user_id] = tariff
        await message.answer(f"Доступ выдан пользователю {user_id} ({tariff}) на {days} дней.")
        await bot.send_message(user_id, f"✅ Доступ к материалам тарифа {tariff.upper()} активирован на {days} дней!", reply_markup=materials_keyboard)
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
            del user_access[user_id]
            user_tariffs.pop(user_id, None)
            await message.answer(f"Доступ для пользователя {user_id} отозван.")
            await bot.send_message(user_id, "❌ Ваш доступ был отозван.")
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
            days = int((user_access[user_id] - time.time()) // 60)
            tariff = user_tariffs.get(user_id, "не указан")
            await message.answer(f"✅ У пользователя {user_id} есть доступ ({tariff.upper()}). Осталось дней: {days}.")
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
/grant [id] [basic/pro] - выдать доступ
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

@dp.callback_query(lambda c: c.data in ["basic", "pro", "offer", "send_screenshot_basic", "send_screenshot_pro", "get_materials"])
async def handle_callback(call: types.CallbackQuery):
    data = call.data
    user_id = call.from_user.id

    if data == "basic":
        user_tariffs[user_id] = "basic"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Оплатить", url="https://pay.kaspi.kz/pay/vx2s6z0c")],
            [InlineKeyboardButton(text="📸 Отправить скриншот", callback_data="send_screenshot_basic")]
        ])
        await call.message.answer("Базовый тариф: 10 000 KZT", reply_markup=keyboard)

    elif data == "pro":
        user_tariffs[user_id] = "pro"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Оплатить", url="https://pay.kaspi.kz/pay/vx2s6z0c")],
            [InlineKeyboardButton(text="📸 Отправить скриншот", callback_data="send_screenshot_pro")]
        ])
        await call.message.answer("ПРО тариф: 250 000 KZT", reply_markup=keyboard)

    elif data == "offer":
        offer_text = (
            "*ПУБЛИЧНАЯ ОФЕРТА*\n"
            "*о заключении договора на предоставление информационно-консультационных услуг*\n\n"

            "*1. Общие положения*\n"
            "1.1. Настоящий документ является официальным предложением (офертой) индивидуального предпринимателя (далее — «Исполнитель») заключить договор на условиях, изложенных ниже.\n"
            "1.2. В соответствии с пунктом 5 статьи 395 Гражданского кодекса Республики Казахстан, данный документ считается публичной офертой.\n"
            "1.3. Полным и безоговорочным принятием настоящей оферты является факт оплаты Заказчиком услуг Исполнителя.\n\n"

            "*2. Предмет договора*\n"
            "2.1. Исполнитель оказывает информационно-консультационные услуги по теме пенсионного обеспечения в Республике Казахстан, включая доступ к обучающим материалам, видео, текстам и другим формам информации в рамках выбранного тарифа.\n\n"

            "*3. Условия предоставления услуг*\n"
            "3.1. Услуги предоставляются через Telegram-бот «СВОЯ ПЕНСИЯ» после подтверждения оплаты.\n"
            "3.2. Услуги оказываются в виде доступа к информационным материалам, с возможностью задать вопрос после активации тарифа.\n"
            "3.3. Срок доступа: 7 календарных дней для базового тарифа с момента активации, 30 дней для тарифа ПРО с момента активации.\n\n"

            "*4. Стоимость и порядок оплаты*\n"
            "4.1. Стоимость услуг составляет:\n"
            "— Базовый тариф: 10 000 тенге\n"
            "— Тариф ПРО: 250 000 тенге\n"
            "4.2. Оплата производится через Kaspi Pay на реквизиты, указанные в боте.\n"
            "4.3. После оплаты Заказчик обязан отправить подтверждение (скриншот) администратору бота.\n\n"

            "*5. Возврат денежных средств*\n"
            "5.1. Заказчик имеет право потребовать возврат денежных средств в течение 2 (двух) календарных дней с момента активации доступа.\n"
            "5.2. Основания для возврата могут включать:\n"
            "– технические сбои (непредоставление доступа, неработающий бот, проблемы с загрузкой материалов);\n"
            "– двойная или ошибочная оплата;\n"
            "– существенное расхождение между заявленным и фактическим содержанием тарифа;\n"
            "5.3. Возврат осуществляется по запросу через службу поддержки: wa.me/77754850900\n"
            "5.4. Средства возвращаются на тот же способ, которым была произведена оплата, в течение 5 рабочих дней с момента одобрения возврата.\n\n"

            "*6. Ответственность сторон*\n"
            "6.1. Исполнитель не несёт ответственности за невозможность использования материалов, если Заказчик не соблюдает технические условия или имеет ограниченный доступ к Telegram.\n"
            "6.2. Все материалы носят информационно-консультационный характер и не являются официальным расчётом пенсионных выплат, выданным государственными органами.\n\n"

            "*7. Заключительные положения*\n"
            "7.1. Исполнитель оставляет за собой право изменять условия настоящей оферты, не противоречащие действующему законодательству.\n"
            "7.2. Заказчик подтверждает, что ознакомлен с условиями оферты и принимает их без оговорок.\n\n"

            "*ИП БАЯНТАЕВА*\n"
            "БИН: 620613400018\n"
            "Реквизиты для оплаты через Kaspi Pay: ИП БАЯНТАЕВА"
        )
        await call.message.answer(offer_text, parse_mode="Markdown")


    elif data == "get_materials":
        if user_id not in user_access or user_access[user_id] < time.time():
            return await call.message.answer("❌ У вас нет активного доступа.")
        tariff = user_tariffs.get(user_id)
        if tariff == "pro":
            await call.message.answer("🔗 Ссылка на канал: https://t.me/yourchannel")
        elif tariff == "basic":
            try:
                archive = InputFile("materials.zip")
                await call.message.answer("📦 Вот архив с материалами:")
                await call.message.answer_document(archive)
            except Exception as e:
                await call.message.answer(f"Ошибка при отправке архива: {e}")
        else:
            await call.message.answer("❗ Не удалось определить ваш тариф. Обратитесь в поддержку.")

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
        f"💳 Тариф: {tariff.upper() if tariff else 'не выбран'}"
    )
    await message.answer(f"Спасибо за скриншот! Вы выбрали тариф: {tariff.upper()}")
    await bot.send_message(ADMIN_ID, info)
    await bot.send_photo(chat_id=ADMIN_ID, photo=message.photo[-1].file_id, caption="Скриншот оплаты")

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
