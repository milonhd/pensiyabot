import time
import logging
import aiopg
from datetime import datetime

from config import DATABASE_URL
from database.models import CREATE_USER_ACCESS_TABLE, CREATE_FISCAL_CHECKS_TABLE

logger = logging.getLogger(__name__)

async def create_pool():
    """Создание пула соединений с базой данных"""
    return await aiopg.create_pool(DATABASE_URL)

async def init_db():
    """Инициализация базы данных и создание таблиц"""
    pool = await create_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            # Создаем таблицы
            await cur.execute(CREATE_USER_ACCESS_TABLE)
            await cur.execute(CREATE_FISCAL_CHECKS_TABLE)
    pool.close()
    await pool.wait_closed()

async def set_user_access(user_id, expire_time, tariff):
    """Установка или обновление уровня доступа пользователя"""
    pool = await create_pool()
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                # Не перезаписываем существующий активный доступ
                await cur.execute("""
                INSERT INTO user_access (user_id, expire_time, tariff)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE 
                SET 
                    expire_time = CASE 
                        WHEN EXCLUDED.expire_time IS NOT NULL THEN EXCLUDED.expire_time 
                        ELSE user_access.expire_time 
                    END,
                    tariff = CASE 
                        WHEN user_access.expire_time IS NULL OR user_access.expire_time < EXTRACT(epoch FROM NOW()) THEN EXCLUDED.tariff 
                        ELSE user_access.tariff 
                    END
                """, (user_id, expire_time, tariff))
    except Exception as e:
        logger.error(f"Ошибка при обновлении доступа: {e}")
        raise
    finally:
        pool.close()
        await pool.wait_closed()

async def get_user_access(user_id):
    """Получение информации о доступе пользователя"""
    pool = await create_pool()
    result = None, None
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT expire_time, tariff FROM user_access WHERE user_id = %s", (user_id,))
                row = await cur.fetchone()
                if row:
                    result = row[0], row[1]
    except Exception as e:
        logger.error(f"Ошибка при получении доступа: {e}")
    finally:
        pool.close()
        await pool.wait_closed()
    return result

async def revoke_user_access(user_id):
    """Отзыв доступа пользователя"""
    pool = await create_pool()
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    UPDATE user_access 
                    SET expire_time = EXTRACT(epoch FROM NOW()) - 1 
                    WHERE user_id = %s
                """, (user_id,))
    except Exception as e:
        logger.error(f"Ошибка при отзыве доступа: {e}")
        raise
    finally:
        pool.close()
        await pool.wait_closed()

async def delete_user_access(user_id):
    """Удаление записи о доступе пользователя"""
    pool = await create_pool()
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM user_access WHERE user_id = %s", (user_id,))
    except Exception as e:
        logger.error(f"Ошибка при удалении доступа: {e}")
    finally:
        pool.close()
        await pool.wait_closed()

async def get_all_active_users():
    """Получение всех пользователей с активным доступом"""
    pool = await create_pool()
    result = []
    current_time = time.time()
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT user_id, expire_time, tariff FROM user_access WHERE expire_time > %s", (current_time,))
                result = await cur.fetchall()
    except Exception as e:
        logger.error(f"Ошибка при получении активных пользователей: {e}")
    finally:
        pool.close()
        await pool.wait_closed()
    return result

async def get_expired_users():
    """Получение пользователей с истекшим доступом"""
    pool = await create_pool()
    result = []
    current_time = time.time()
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT user_id, tariff FROM user_access WHERE expire_time <= %s", (current_time,))
                result = await cur.fetchall()
    except Exception as e:
        logger.error(f"Ошибка при получении пользователей с истекшим доступом: {e}")
    finally:
        pool.close()
        await pool.wait_closed()
    return result

async def save_user(user):
    """Сохранение информации о пользователе"""
    pool = await create_pool()
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    INSERT INTO user_access (user_id, username, first_name, last_name)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE 
                    SET 
                        username = EXCLUDED.username,
                        first_name = EXCLUDED.first_name,
                        last_name = EXCLUDED.last_name
                """, (user.id, user.username, user.first_name, user.last_name))
    except Exception as e:
        logger.error(f"Ошибка при сохранении пользователя: {e}")
    finally:
        pool.close()
        await pool.wait_closed()

async def get_all_users():
    """Получение списка всех пользователей"""
    pool = await create_pool()
    users = []
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT user_id FROM user_access")
                rows = await cur.fetchall()
                users = [row[0] for row in rows]
    except Exception as e:
        logger.error(f"Ошибка при получении всех пользователей: {e}")
    finally:
        pool.close()
        await pool.wait_closed()
    return users

async def check_duplicate_file(file_id):
    """Проверка на дубликат файла чека"""
    pool = await create_pool()
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1 FROM fiscal_checks WHERE file_id = %s", (file_id,))
                return await cur.fetchone() is not None
    except Exception as e:
        logger.error(f"Ошибка при проверке дубликата файла: {e}")
        return False
    finally:
        pool.close()
        await pool.wait_closed()

async def save_receipt(user_id, amount, check_number, fp, date_time, buyer_name, file_id):
    """Сохранение информации о чеке"""
    pool = None
    try:
        pool = await create_pool()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    INSERT INTO fiscal_checks 
                    (user_id, amount, check_number, fp, date_time, buyer_name, file_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (user_id, amount, check_number, fp, date_time, buyer_name, file_id))
                return True
    except Exception as e:
        logger.error(f"Ошибка при сохранении чека: {e}")
        return False
    finally:
        if pool:
            pool.close()
            await pool.wait_closed()
