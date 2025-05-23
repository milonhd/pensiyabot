# config.py
import os
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()

API_TOKEN = os.getenv('API_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID'))

# Получаем GROUP_IDS безопасно. Если переменная не установлена, используем пустую строку.
group_ids_str = os.getenv('GROUP_IDS', '')
GROUP_IDS = [int(g_id) for g_id in group_ids_str.split(',') if g_id.strip()]

RECEIPT_DIR = os.getenv('RECEIPT_DIR', '/app/receipts')
DATABASE_URL = os.getenv('DATABASE_URL')

if not API_TOKEN:
    raise ValueError("API_TOKEN не установлен в .env")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL не установлен в .env")
if not ADMIN_ID:
    raise ValueError("ADMIN_ID не установлен в .env")
# Проверяем, что GROUP_IDS не пуст после обработки
if not GROUP_IDS:
    raise ValueError("GROUP_IDS не установлен или пуст в .env (пример: -123456789,-987654321)")

os.makedirs(RECEIPT_DIR, exist_ok=True)
