import aiopg
import time
from datetime import datetime
from config import DATABASE_URL

async def create_pool():
    return await aiopg.create_pool(DATABASE_URL)

async def init_db():
    pool = await create_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
            CREATE TABLE IF NOT EXISTS user_access (
                user_id BIGINT PRIMARY KEY,
                expire_time BIGINT,
                tariff VARCHAR(20)
            )
            """)
            await cur.execute("""
                ALTER TABLE user_access
                ADD COLUMN IF NOT EXISTS username VARCHAR(255),
                ADD COLUMN IF NOT EXISTS first_name VARCHAR(255),
                ADD COLUMN IF NOT EXISTS last_name VARCHAR(255),
                ADD COLUMN IF NOT EXISTS joined_at TIMESTAMP DEFAULT NOW()
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
    pool.close()
    await pool.wait_closed()

async def save_receipt(user_id, amount, check_number, fp, date_time, buyer_name, file_id):
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
        import logging
        logging.error(f"Ошибка при сохранении чека: {e}")
        return False
    finally:
        if pool:
            pool.close()
            await pool.wait_closed()

async def check_duplicate_file(file_id):
    pool = await create_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT 1 FROM fiscal_checks WHERE file_id = %s", (file_id,))
            return await cur.fetchone() is not None
    pool.close()
    await pool.wait_closed()

async def set_user_access(user_id, expire_time, tariff):
    pool = await create_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
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
    pool.close()
    await pool.wait_closed()

async def get_user_access(user_id):
    pool = await create_pool()
    result = None, None
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT expire_time, tariff FROM user_access WHERE user_id = %s", (user_id,))
            row = await cur.fetchone()
            if row:
                result = row[0], row[1]
    pool.close()
    await pool.wait_closed()
    return result

async def revoke_user_access(user_id):
    pool = await create_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                UPDATE user_access
                SET expire_time = EXTRACT(epoch FROM NOW()) - 1
                WHERE user_id = %s
            """, (user_id,))
    pool.close()
    await pool.wait_closed()

async def get_all_active_users():
    pool = await create_pool()
    result = []
    current_time = time.time()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT user_id, expire_time, tariff FROM user_access WHERE expire_time > %s", (current_time,))
            result = await cur.fetchall()
    pool.close()
    await pool.wait_closed()
    return result

async def get_expired_users():
    pool = await create_pool()
    result = []
    current_time = time.time()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT user_id, tariff FROM user_access WHERE expire_time <= %s", (current_time,))
            result = await cur.fetchall()
    pool.close()
    await pool.wait_closed()
    return result

async def save_user(user):
    pool = await create_pool()
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
    pool.close()
    await pool.wait_closed()

async def get_all_users():
    pool = await create_pool()
    users = []
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT user_id FROM user_access")
            rows = await cur.fetchall()
            users = [row[0] for row in rows]
    pool.close()
    await pool.wait_closed()
    return users

async def delete_user_access(user_id):
    pool = await create_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM user_access WHERE user_id = %s", (user_id,))
    pool.close()
    await pool.wait_closed()
