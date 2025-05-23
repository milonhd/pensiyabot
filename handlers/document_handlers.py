import logging
import os
import re
import time
import pdfplumber
from aiogram.enums import ChatType
from datetime import datetime
from aiogram import F, Bot, types, Dispatcher
from database import get_user_access, set_user_access, save_receipt, check_duplicate_file
from config import ADMIN_ID, RECEIPT_DIR
from keyboards import materials_keyboard # Для отправки после активации

logger = logging.getLogger(__name__)

async def parse_kaspi_receipt(pdf_path: str):
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = "\n".join(page.extract_text() for page in pdf.pages)

            data = {
                "amount": float(re.search(r"(\d+)\s*₸", text).group(1)) if re.search(r"(\d+)\s*₸", text) else None,
                "iin": re.search(r"ИИН/БИН продавца\s*(\d+)", text).group(1) if re.search(r"ИИН/БИН продавца\s*(\d+)", text) else None,
                "check_number": re.search(r"№ чека\s*(\S+)", text).group(1) if re.search(r"№ чека\s*(\S+)", text) else None,
                "fp": re.search(r"ФП\s*(\d+)", text).group(1) if re.search(r"ФП\s*(\d+)", text) else None,
                "date_time": re.search(r"Дата и время\s*(?:по Астане)?\s*(\d{2}\.\d{2}\.\d{4} \d{2}:\d{2})", text).group(1) if re.search(r"Дата и время\s*(?:по Астане)?\s*(\d{2}\.\d{2}\.\d{4} \d{2}:\d{2})", text) else None,
                "buyer_name": re.search(r"ФИО покупателя\s*(.+)", text).group(1).strip() if re.search(r"ФИО покупателя\s*(.+)", text) else None
            }
            return data
    except Exception as e:
        logger.error(f"Ошибка парсинга PDF: {e}")
        return None

@F.document
@F.chat.type == ChatType.PRIVATE
async def handle_document(message: types.Message, bot: Bot):
    logger.info(f"Получен документ: {message.document.file_name}")
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
        f"Данные чека:\n"
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

    if tariff and receipt_data["amount"] != required_amounts.get(tariff, 0):
        errors.append(f"Сумма не соответствует выбранному тарифу {tariff.upper()}")
    elif not tariff:
        errors.append("Тариф для пользователя не установлен. Пожалуйста, выберите тариф.")


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

    # Автоматическая активация доступа
    if tariff in ["self", "basic", "pro"] + [str(y) for y in range(2025, 2032)]:
        duration = {
            "self": 7,
            "basic": 30,
            "pro": 60,
            **{str(y): 7 for y in range(2025, 2032)}
        }.get(tariff, 7) * 86400

        # Если доступ уже активен, не продлеваем его автоматически при повторной отправке чека
        if not expire_time or expire_time <= time.time():
            await set_user_access(user.id, time.time() + duration, tariff)
            await message.answer(
                f"✅ Доступ уровня {tariff.upper()} активирован на {duration//86400} дней!",
                reply_markup=materials_keyboard
            )
        else:
            await message.answer("✅ Чек успешно загружен! Ваш доступ уже активен.")


    info = (
        f"📄 Фискальный чек от пользователя:\n"
        f"🆔 ID: {user.id}\n"
        f"👤 Username: @{user.username or 'Без username'}\n"
        f"💳 Уровень: {tariff.upper() if tariff else 'не выбран'}\n"
        f"📝 Файл: {message.document.file_name}"
    )

    await bot.send_message(ADMIN_ID, info)
    await bot.send_document(ADMIN_ID, message.document.file_id)

def register_document_handlers(dp: Dispatcher):
    dp.message.register(handle_document, F.document)