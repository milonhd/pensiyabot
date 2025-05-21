import logging
import asyncio
import time
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database.operations import (
    get_all_active_users,
    get_expired_users,
    delete_user_access
)
from config import ADMIN_ID, GROUP_IDS

logger = logging.getLogger(__name__)

class SchedulerService:
    def __init__(self, bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler(timezone="UTC")
        
    def start(self):
        """Запускает все запланированные задачи"""
        # Периодическая проверка истекших доступов
        self.scheduler.add_job(
            self.check_access_periodically,
            'interval',
            seconds=10,
            id='check_access'
        )
        
        # Уведомление пользователей об истечении срока доступа
        self.scheduler.add_job(
            self.check_subscriptions,
            'interval', 
            hours=1,
            id='check_subscriptions'
        )
        
        self.scheduler.start()
        logger.info("Планировщик задач запущен")
    
    def shutdown(self):
        """Останавливает планировщик"""
        self.scheduler.shutdown()
        logger.info("Планировщик задач остановлен")
    
    async def check_access_periodically(self):
        """Проверяет истекшие доступы и удаляет пользователей из групп"""
        try:
            expired_users = await get_expired_users()

            for user_id, tariff in expired_users:
                # Удаление из групп
                for group_id in GROUP_IDS:
                    try:
                        await self.bot.ban_chat_member(group_id, user_id)  # бан
                        await self.bot.unban_chat_member(group_id, user_id)  # сразу разбан, чтобы можно было вернуться
                        logger.info(f"Пользователь {user_id} удалён из группы {group_id}")
                    except Exception as e:
                        logger.warning(f"Не удалось удалить пользователя {user_id} из группы {group_id}: {e}")

                # Уведомление пользователя
                try:
                    await self.bot.send_message(user_id, "❌ Ваш доступ истёк. Вы были удалены из группы.")
                except Exception as e:
                    logger.warning(f"Не удалось отправить уведомление пользователю {user_id}: {e}")

                # Уведомление администратора
                try:
                    await self.bot.send_message(
                        ADMIN_ID,
                        f"⛔️ Пользователь {user_id} был удалён из групп, доступ истёк ({tariff})."
                    )
                except Exception as e:
                    logger.warning(f"Не удалось отправить уведомление администратору: {e}")

                # Удаляем из базы данных
                await delete_user_access(user_id)

        except Exception as e:
            logger.error(f"Ошибка в проверке доступа: {e}")

    async def check_subscriptions(self):
        """Уведомляет пользователей об истечении срока подписки"""
        try:
            users = await get_all_active_users()
            for user_id, expire_time, _ in users:
                if (expire_time - time.time()) < 86400 * 3:  # За 3 дня до истечения
                    await self.bot.send_message(
                        user_id,
                        f"⚠️ Ваш доступ истекает через 3 дня!"
                    )
        except Exception as e:
            logger.error(f"Ошибка при проверке подписок: {e}")

    async def execute_scheduled_broadcast(self, content: dict, recipients=None):
        """Выполняет отложенную рассылку"""
        from database.operations import get_all_users
        
        users = recipients if recipients else await get_all_users()
        
        success = 0
        errors = 0
        
        for user_id in users:
            try:
                if content.get('photo'):
                    await self.bot.send_photo(
                        chat_id=user_id,
                        photo=content['photo'],
                        caption=content.get('text', ''),
                        parse_mode='HTML'
                    )
                elif content.get('video'):
                    await self.bot.send_video(
                        chat_id=user_id,
                        video=content['video'],
                        caption=content.get('text', ''),
                        parse_mode='HTML'
                    )
                elif content.get('document'):
                    await self.bot.send_document(
                        chat_id=user_id,
                        document=content['document'],
                        caption=content.get('text', ''),
                        parse_mode='HTML'
                    )
                else:
                    await self.bot.send_message(
                        chat_id=user_id,
                        text=content.get('text', ''),
                        parse_mode='HTML'
                    )
                
                success += 1
                # Небольшая пауза, чтобы избежать лимитов Telegram
                await asyncio.sleep(0.05)
                
            except Exception as e:
                errors += 1
                logger.error(f"Ошибка отправки запланированного сообщения пользователю {user_id}: {e}")
                await asyncio.sleep(1)  # При ошибке делаем паузу подольше
        
        # Отправляем отчет админу
        report_message = (
            f"📊 Запланированная рассылка выполнена!\n\n"
            f"👥 Всего пользователей: {len(users)}\n"
            f"✅ Успешно отправлено: {success}\n"
            f"❌ Ошибок: {errors}\n"
            f"📈 Успешных доставок: {int(success/len(users)*100 if users else 0)}%"
        )
        
        await self.bot.send_message(ADMIN_ID, report_message)
    
    def schedule_broadcast(self, content: dict, scheduled_time=None, recipients=None):
        """Добавляет в планировщик задачу на рассылку в указанное время"""
        if scheduled_time:
            # Добавляем задачу на определенное время
            job_id = f"broadcast_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            self.scheduler.add_job(
                self.execute_scheduled_broadcast,
                'date',
                run_date=scheduled_time,
                args=[content, recipients],
                id=job_id
            )
            return job_id
        else:
            # Выполняем немедленно
            asyncio.create_task(self.execute_scheduled_broadcast(content, recipients))
            return None
