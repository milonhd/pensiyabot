# utils.py
import asyncio
import time
import logging
from aiogram import Bot
from keyboards import main_keyboard
from database import get_expired_users, get_all_active_users, delete_user_access

logger = logging.getLogger(__name__)

async def check_access_periodically(bot: Bot, ADMIN_ID: int, GROUP_IDS: list, delete_user_access_func):
    while True:
        try:
            expired_users = await get_expired_users()

            for user_id, tariff in expired_users:
                for group_id in GROUP_IDS:
                    try:
                        await bot.ban_chat_member(group_id, user_id)
                        await bot.unban_chat_member(group_id, user_id)
                        logger.info(f"Пользователь {user_id} удалён из группы {group_id}")
                    except Exception as e:
                        logger.warning(f"Не удалось удалить пользователя {user_id} из группы {group_id}: {e}")

                try:
                    await bot.send_message(user_id, "❌ Ваш доступ истёк. Вы были удалены из группы.")
                except Exception as e:
                    logger.warning(f"Не удалось отправить уведомление пользователю {user_id}: {e}")

                try:
                    await bot.send_message(
                        ADMIN_ID,
                        f"⛔️ Пользователь {user_id} был удалён из групп, доступ истёк ({tariff})."
                    )
                except Exception as e:
                    logger.warning(f"Не удалось отправить уведомление администратору: {e}")

                await delete_user_access_func(user_id)
        except Exception as e:
            logger.error(f"Ошибка в проверке доступа: {e}")

        await asyncio.sleep(10)

async def check_subscriptions(bot: Bot):
    while True:
        users = await get_all_active_users()
        for user_id, expire_time, _ in users:
            if (expire_time - time.time()) < 86400 * 3:
                try:
                    await bot.send_message(
                        user_id,
                        f"⚠️ Ваш доступ истекает через 3 дня!",
                        reply_markup=main_keyboard
                    )
                except Exception as e:
                    logger.warning(f"Не удалось отправить уведомление об истечении подписки пользователю {user_id}: {e}")
        await asyncio.sleep(3600)
