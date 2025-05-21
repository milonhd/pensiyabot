import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram import F
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import API_TOKEN, ADMIN_ID
from database import init_db
from handlers.admin import register_admin_handlers
from handlers.broadcast import register_broadcast_handlers
from handlers.common import register_common_handlers
from handlers.subscription import register_subscription_handlers, check_access_periodically
from handlers.receipt import register_receipt_handlers
from utils.commands import delete_bot_commands

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler(timezone="UTC")

# Создание директории для чеков если не существует
RECEIPT_DIR = "/app/receipts"
os.makedirs(RECEIPT_DIR, exist_ok=True)

# Регистрация всех обработчиков
def register_all_handlers():
    # Игнорирование групповых сообщений
    dp.message.register(lambda message: None, F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
    
    # Регистрация обработчиков из разных модулей
    register_admin_handlers(dp, bot)
    register_common_handlers(dp, bot)
    register_subscription_handlers(dp, bot)
    register_receipt_handlers(dp, bot)
    register_broadcast_handlers(dp, bot)

async def on_startup():
    """Действия при запуске бота"""
    await init_db()
    await delete_bot_commands(bot)
    # Запуск периодической проверки доступов
    asyncio.create_task(check_access_periodically(bot))
    logger.info("Бот запущен")
    scheduler.start()

async def on_shutdown():
    """Действия при остановке бота"""
    scheduler.shutdown()
    await bot.session.close()
    logger.info("Бот остановлен")

def main():
    """Основная функция запуска бота"""
    register_all_handlers()
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    try:
        asyncio.run(dp.start_polling(bot))
    except (KeyboardInterrupt, SystemExit):
        logger.warning("Бот остановлен")

if __name__ == "__main__":
    main()
