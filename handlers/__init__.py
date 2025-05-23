from aiogram import Dispatcher
from aiogram.types import BotCommandScopeAllPrivateChats
import logging

from . import admin_handlers
from . import user_handlers
from . import callback_handlers
from . import document_handlers

logger = logging.getLogger(__name__)

async def delete_bot_commands(bot):
    await bot.delete_my_commands(scope=BotCommandScopeAllPrivateChats())
    await bot.delete_my_commands()

async def on_startup_actions(bot):
    await delete_bot_commands(bot)
    logger.info("Бот запущен!")

async def on_shutdown_actions(bot):
    await bot.session.close()
    logger.info("Бот остановлен.")

def register_all_handlers(dp: Dispatcher):
    admin_handlers.register_admin_handlers(dp)
    user_handlers.register_user_handlers(dp)
    callback_handlers.register_callback_handlers(dp)
    document_handlers.register_document_handlers(dp)

    # Обработчики сообщений из групп (игнорирование)
    dp.message.register(user_handlers.ignore_group_messages)