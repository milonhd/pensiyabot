import os
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()

API_TOKEN = os.getenv('API_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID'))
# Разделяем строку GROUP_IDS по запятой и преобразуем в список целых чисел
GROUP_IDS = [int(g_id) for g_id in os.getenv('GROUP_IDS').split(',')]
RECEIPT_DIR = os.getenv('RECEIPT_DIR', '/app/receipts') # Добавлено значение по умолчанию
DATABASE_URL = os.getenv('DATABASE_URL')

if not API_TOKEN:
    raise ValueError("API_TOKEN не установлен в .env")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL не установлен в .env")
if not ADMIN_ID:
    raise ValueError("ADMIN_ID не установлен в .env")
if not GROUP_IDS:
    raise ValueError("GROUP_IDS не установлен в .env")

os.makedirs(RECEIPT_DIR, exist_ok=True)
