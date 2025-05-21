import logging
import re
from datetime import datetime
import pdfplumber

logger = logging.getLogger(__name__)

async def parse_kaspi_receipt(pdf_path: str):
    """
    Парсит PDF-файл фискального чека Kaspi для извлечения важной информации.
    
    Args:
        pdf_path (str): Путь к PDF-файлу чека
        
    Returns:
        dict: Словарь с извлеченными данными или None в случае ошибки
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = "\n".join(page.extract_text() for page in pdf.pages)
            
            # Извлекаем необходимые данные с помощью регулярных выражений
            data = {
                "amount": float(re.search(r"(\d+)\s*₸", text).group(1)) if re.search(r"(\d+)\s*₸", text) else None,
                "iin": re.search(r"ИИН/БИН продавца\s*(\d+)", text).group(1) if re.search(r"ИИН/БИН продавца\s*(\d+)", text) else None,
                "check_number": re.search(r"№ чека\s*(\S+)", text).group(1) if re.search(r"№ чека\s*(\S+)", text) else None,
                "fp": re.search(r"ФП\s*(\d+)", text).group(1) if re.search(r"ФП\s*(\d+)", text) else None,
                "date_time": re.search(r"Дата и время\s*(?:по Астане)?\s*(\d{2}\.\d{2}\.\d{4} \d{2}:\d{2})", text).group(1) 
                            if re.search(r"Дата и время\s*(?:по Астане)?\s*(\d{2}\.\d{2}\.\d{4} \d{2}:\d{2})", text) else None,
                "buyer_name": re.search(r"ФИО покупателя\s*(.+)", text).group(1).strip() 
                              if re.search(r"ФИО покупателя\s*(.+)", text) else None
            }
            
            # Валидация извлеченных данных
            required_fields = ["amount", "check_number", "fp", "date_time", "iin"]
            for field in required_fields:
                if data[field] is None:
                    logger.warning(f"В чеке отсутствует обязательное поле: {field}")
            
            return data
    except Exception as e:
        logger.error(f"Ошибка парсинга PDF: {e}")
        return None

def validate_receipt_data(data, required_amount=None, required_iin="620613400018"):
    """
    Проверяет данные чека на соответствие требованиям
    
    Args:
        data (dict): Словарь с данными чека
        required_amount (float, optional): Требуемая сумма платежа
        required_iin (str, optional): Требуемый ИИН/БИН получателя
        
    Returns:
        tuple: (bool, list) - результат проверки и список ошибок
    """
    if not data:
        return False, ["Не удалось прочитать данные чека"]
    
    errors = []
    
    # Проверка ИИН/БИН
    if data.get("iin") != required_iin:
        errors.append("ИИН продавца не совпадает")
    
    # Проверка суммы, если она указана
    if required_amount is not None and data.get("amount") != required_amount:
        errors.append(f"Сумма не соответствует требуемой ({required_amount})")
    
    # Проверка наличия других обязательных полей
    required_fields = ["check_number", "fp", "date_time"]
    for field in required_fields:
        if not data.get(field):
            errors.append(f"Отсутствует поле {field}")
    
    # Преобразование даты для проверки формата
    if data.get("date_time"):
        try:
            datetime.strptime(data["date_time"], "%d.%m.%Y %H:%M")
        except ValueError:
            errors.append("Неверный формат даты")
    
    return len(errors) == 0, errors

def format_receipt_info(data):
    """
    Форматирует данные чека для отображения пользователю
    
    Args:
        data (dict): Словарь с данными чека
        
    Returns:
        str: Отформатированная строка с информацией
    """
    if not data:
        return "Данные чека отсутствуют"
        
    info = f"📝 Данные чека:\n"
    
    if data.get("iin"):
        info += f"ИИН/БИН: {data['iin']}\n"
    
    if data.get("amount"):
        info += f"Сумма: {data['amount']} ₸\n"
    
    if data.get("check_number"):
        info += f"Номер чека: {data['check_number']}\n"
    
    if data.get("date_time"):
        info += f"Дата: {data['date_time']}\n"
    
    if data.get("buyer_name"):
        info += f"Покупатель: {data['buyer_name']}\n"
        
    return info
