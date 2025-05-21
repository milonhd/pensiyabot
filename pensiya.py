import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from config import Config
from database import Database
from handlers import register_handlers
from logging_config import setup_logging
from constants import GROUP_IDS
from utils import check_access_periodically, check_subscriptions

async def on_startup(db: Database, bot: Bot, scheduler: AsyncIOScheduler, admin_id: int):
    """Инициализация ресурсов бота при запуске."""
    await db.init_db()
    await bot.delete_my_commands()  # Удаление стандартных команд
    scheduler.add_job(check_access_periodically, 'interval', seconds=10, args=(db, bot, admin_id, GROUP_IDS))
    scheduler.add_job(check_subscriptions, 'interval', seconds=3600, args=(db, bot))
    scheduler.start()
    logging.info("Бот успешно запущен")

async def on_shutdown(db: Database, scheduler: AsyncIOScheduler, bot: Bot):
    """Очистка ресурсов при остановке бота."""
    scheduler.shutdown()
    await bot.session.close()
    await db.close()
    logging.info("Бот остановлен")

async def main():
    """Основная точка входа для бота."""
    # Настройка логирования
    setup_logging()
    
    # Загрузка конфигурации
    config = Config()
    
    # Инициализация бота и диспетчера
    bot = Bot(token=config.api_token)
    dp = Dispatcher(storage=MemoryStorage())
    
    # Инициализация базы данных
    db = Database(config.database_url)
    
    # Инициализация планировщика
    scheduler = AsyncIOScheduler(timezone="UTC")
    
    # Регистрация обработчиков
    register_handlers(dp, db, bot, config.admin_id, GROUP_IDS)
    
    # Регистрация хуков запуска и остановки
    dp.startup.register(lambda: on_startup(db, bot, scheduler, config.admin_id))
    dp.shutdown.register(lambda: on_shutdown(db, scheduler, bot))
    
    try:
        await dp.start_polling(bot)
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен пользователем")
    except Exception as e:
        logging.error(f"Критическая ошибка: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())
