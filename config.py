import os

API_TOKEN = '7940234323:AAG0GVXl_k4oLefRsZnte-S8PYUvowv2gVU'  #
ADMIN_ID = 1640165074  #
GROUP_IDS = [-1002583988789, -1002529607781, -1002611068580, -1002607289832, -1002560662894, -1002645685285, -1002529375771, -1002262602915]  #
RECEIPT_DIR = "/app/receipts"  #

# Конфигурация для PostgreSQL
DATABASE_URL = os.environ.get('DATABASE_URL')  #
if not DATABASE_URL: #
    # Локальная конфигурация для тестирования
    DATABASE_URL = "postgres://username:password@localhost:5432/telegrambot" #

os.makedirs(RECEIPT_DIR, exist_ok=True) #