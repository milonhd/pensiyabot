import os
import logging
import aiopg
import time
from aiogram import types
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    DATABASE_URL = "postgres://username:password@localhost:5432/telegrambot"

db_pool = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def create_db_pool():
    global db_pool
    try:
        db_pool = await aiopg.create_pool(DATABASE_URL, minsize=5, maxsize=20)
        logger.info("Пул подключений к БД создан успешно")
    except Exception as e:
        logger.error(f"Ошибка создания пула БД: {e}")
        raise

async def close_db_pool():
    global db_pool
    if db_pool:
        db_pool.close()
        await db_pool.wait_closed()
        logger.info("Пул подключений к БД закрыт")

async def get_db_connection():
    if not db_pool:
        raise Exception("Пул БД не инициализирован")
    return db_pool.acquire()

async def init_db():
    async with await get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
            CREATE TABLE IF NOT EXISTS user_access (
                user_id BIGINT PRIMARY KEY,
                expire_time TIMESTAMP,
                tariff VARCHAR(20),
                username VARCHAR(255),
                first_name VARCHAR(255),
                last_name VARCHAR(255),
                joined_at TIMESTAMP DEFAULT NOW(),
                last_activity TIMESTAMP DEFAULT NOW()
            )
            """)
            
            await cur.execute("""
            ALTER TABLE user_access 
            ADD COLUMN IF NOT EXISTS last_activity TIMESTAMP DEFAULT NOW()
            """)
            
            await cur.execute("""
            CREATE TABLE IF NOT EXISTS fiscal_checks (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES user_access(user_id),
                amount DECIMAL,
                check_number VARCHAR(50) UNIQUE,
                fp VARCHAR(50) UNIQUE,
                date_time TIMESTAMP,
                buyer_name VARCHAR(255),
                file_id VARCHAR(255) UNIQUE,
                created_at TIMESTAMP DEFAULT NOW()
            )
            """)
            
            await cur.execute("CREATE INDEX IF NOT EXISTS idx_user_access_expire ON user_access(expire_time)")
            await cur.execute("CREATE INDEX IF NOT EXISTS idx_fiscal_checks_user_id ON fiscal_checks(user_id)")
            await cur.execute("CREATE INDEX IF NOT EXISTS idx_fiscal_checks_created_at ON fiscal_checks(created_at)")

async def save_receipt(user_id, amount, check_number, fp, date_time, buyer_name, file_id):
    try:
        async with await get_db_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    INSERT INTO fiscal_checks 
                    (user_id, amount, check_number, fp, date_time, buyer_name, file_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (user_id, amount, check_number, fp, date_time, buyer_name, file_id))
                return True
    except Exception as e:
        logging.error(f"Ошибка при сохранении чека: {e}")
        return False

async def check_duplicate_file(file_id):
    async with await get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT 1 FROM fiscal_checks WHERE file_id = %s", (file_id,))
            return await cur.fetchone() is not None

async def set_user_access(user_id: int, duration_days: int, tariff: str) -> bool:
    global db_pool 
    
    expire_time = datetime.now() + timedelta(days=duration_days)
    try:
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    INSERT INTO user_access (user_id, expire_time, tariff)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE 
                    SET 
                        expire_time = EXCLUDED.expire_time,
                        tariff = EXCLUDED.tariff
                """, (user_id, expire_time, tariff))
        return True
    except Exception as e:
        logging.error(f"Ошибка: {e}")
        return False

async def get_user_access(user_id):
    async with await get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT expire_time, tariff 
                FROM user_access 
                WHERE user_id = %s
            """, (user_id,))
            row = await cur.fetchone()
            if row:
                return row[0], row[1]
            return None, None

async def revoke_user_access(user_id):
    async with await get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                UPDATE user_access 
                SET expire_time = NULL
                WHERE user_id = %s
            """, (user_id,))

async def get_all_active_users():
    async with await get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT user_id, expire_time, tariff, username 
                FROM user_access 
                WHERE expire_time > NOW()
            """)
            rows = await cur.fetchall()
            return [(row[0], row[1].timestamp(), row[2], row[3]) for row in rows]

async def get_expired_users():
    async with await get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT user_id, tariff 
                FROM user_access 
                WHERE expire_time IS NOT NULL
                AND expire_time < NOW()
            """)
            return await cur.fetchall()

async def save_user(user: types.User):
    global db_pool
    try:
        if not db_pool:
            await create_db_pool()
        async with await get_db_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                INSERT INTO user_access (user_id, username, first_name, last_name, last_activity)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (user_id) DO UPDATE 
                SET 
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    last_activity = NOW()
            """, (user.id, user.username, user.first_name, user.last_name))

async def get_all_users():
    async with await get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT user_id FROM user_access")
            rows = await cur.fetchall()
            return [row[0] for row in rows]

async def update_user_activity(user_id):
    async with await get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                UPDATE user_access 
                SET last_activity = NOW() 
                WHERE user_id = %s
            """, (user_id,))

async def get_stats():
    async with await get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT COUNT(*) FROM user_access")
            total_users = (await cur.fetchone())[0]
          
            await cur.execute("""
                SELECT COUNT(*) FROM user_access 
                WHERE expire_time > NOW()
            """)
            active_users = (await cur.fetchone())[0]
           
            await cur.execute("""
                SELECT tariff, COUNT(*) 
                FROM user_access 
                WHERE expire_time > NOW()
                GROUP BY tariff
            """)
            tariff_stats = await cur.fetchall()
            
            await cur.execute("""
                SELECT COUNT(*) 
                FROM fiscal_checks 
                WHERE created_at > NOW() - INTERVAL '30 days'
            """)
            receipts_30d = (await cur.fetchone())[0]
          
            await cur.execute("""
                SELECT COUNT(*) 
                FROM user_access 
                WHERE last_activity > NOW() - INTERVAL '7 days'
            """)
            active_7d = (await cur.fetchone())[0]
            
            await cur.execute("""
                SELECT COUNT(*) 
                FROM user_access 
                WHERE joined_at > NOW() - INTERVAL '30 days'
            """)
            new_users_30d = (await cur.fetchone())[0]
          
            await cur.execute("""
                SELECT tariff, COUNT(*) as cnt
                FROM fiscal_checks fc
                JOIN user_access ua ON fc.user_id = ua.user_id
                WHERE fc.created_at > NOW() - INTERVAL '30 days'
                GROUP BY tariff
                ORDER BY cnt DESC
            """)
            popular_tariffs = await cur.fetchall()
            
            return {
                'total_users': total_users,
                'active_users': active_users,
                'tariff_stats': tariff_stats,
                'receipts_30d': receipts_30d,
                'active_7d': active_7d,
                'new_users_30d': new_users_30d,
                'popular_tariffs': popular_tariffs
            }
