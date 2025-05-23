import asyncio
import logging
from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import API_TOKEN, ADMIN_ID, GROUP_IDS, DATABASE_URL, RECEIPT_DIR
from database import init_db, create_pool, delete_user_access
from handlers import register_all_handlers, on_startup_actions, on_shutdown_actions # Изменено
from utils import check_access_periodically, check_subscriptions

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler(timezone="UTC")

async def main():
    dp.startup.register(on_startup_actions)
    dp.shutdown.register(on_shutdown_actions)

    # Инициализация базы данных
    await init_db()

    # Регистрация всех хэндлеров
    register_all_handlers(dp) # Изменено

    # Запуск периодических задач
    asyncio.create_task(check_access_periodically(bot, ADMIN_ID, GROUP_IDS, delete_user_access))
    asyncio.create_task(check_subscriptions(bot))

    try:
        await dp.start_polling(bot)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped")

if __name__ == '__main__':
    asyncio.run(main())
