import logging
import asyncio
from typing import List
from aiogram import Bot
from database import Database
from constants import GROUP_IDS
import keyboards

logger = logging.getLogger(__name__)

async def check_access_periodically(db: Database, bot: Bot, admin_id: int, group_ids: List[int]):
    """Периодическая проверка истекших доступов."""
    while True:
        try:
            expired_users = await db.get_expired_users()
            for user_id, tariff in expired_users:
                for group_id in group_ids:
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
                        admin_id,
                        f"⛔️ Пользователь {user_id} был удалён из групп, доступ истёк ({tariff})."
                    )
                except Exception as e:
                    logger.warning(f"Не удалось отправить уведомление администратору: {e}")
        except Exception as e:
            logger.error(f"Ошибка в проверке доступа: {e}", exc_info=True)
        await asyncio.sleep(10)

async def check_subscriptions(db: Database, bot: Bot):
    """Проверка подписок и отправка уведомлений за 3 дня до истечения."""
    while True:
        try:
            users = await db.get_all_active_users()
            for user_id, expire_time, _ in users:
                if (expire_time - time.time()) < 86400 * 3:
                    await bot.send_message(
                        user_id,
                        f"⚠️ Ваш доступ истекает через 3 дня!",
                        reply_markup=keyboards.main_keyboard()
                    )
        except Exception as e:
            logger.error(f"Ошибка проверки подписок: {e}", exc_info=True)
        await asyncio.sleep(3600)
