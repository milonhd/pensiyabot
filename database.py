import logging
import aiopg
from typing import Optional, List, Tuple
from datetime import datetime
import pdfplumber
import re
import os

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pool = None

    async def create_pool(self) -> aiopg.Pool:
        """Создание пула соединений с базой данных."""
        if not self.pool:
            self.pool = await aiopg.create_pool(self.database_url)
        return self.pool

    async def init_db(self):
        """Инициализация схемы базы данных."""
        async with self.create_pool() as pool:
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("""
                        CREATE TABLE IF NOT EXISTS user_access (
                            user_id BIGINT PRIMARY KEY,
                            expire_time BIGINT,
                            tariff VARCHAR(20),
                            username VARCHAR(255),
                            first_name VARCHAR(255),
                            last_name VARCHAR(255),
                            joined_at TIMESTAMP DEFAULT NOW()
                        )
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
        logger.info("База данных инициализирована")

    async def set_user_access(self, user_id: int, expire_time: Optional[float], tariff: str):
        """Установка или обновление доступа пользователя."""
        async with self.create_pool() as pool:
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
        logger.debug(f"Установлен доступ для пользователя {user_id} с тарифом {tariff}")

    async def get_user_access(self, user_id: int) -> Tuple[Optional[float], Optional[str]]:
        """Получение данных о доступе пользователя."""
        async with self.create_pool() as pool:
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT expire_time, tariff FROM user_access WHERE user_id = %s", (user_id,))
                    row = await cur.fetchone()
                    return row if row else (None, None)

    async def revoke_user_access(self, user_id: int):
        """Отзыв доступа пользователя."""
        async with self.create_pool() as pool:
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("""
                        UPDATE user_access 
                        SET expire_time = EXTRACT(epoch FROM NOW()) - 1 
                        WHERE user_id = %s
                    """, (user_id,))
        logger.info(f"Доступ отозван для пользователя {user_id}")

    async def get_all_active_users(self) -> List[Tuple[int, float, str]]:
        """Получение всех пользователей с активным доступом."""
        current_time = datetime.now().timestamp()
        async with self.create_pool() as pool:
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT user_id, expire_time, tariff FROM user_access WHERE expire_time > %s", (current_time,))
                    return await cur.fetchall()

    async def get_expired_users(self) -> List[Tuple[int, str]]:
        """Получение всех пользователей с истекшим доступом."""
        current_time = datetime.now().timestamp()
        async with self.create_pool() as pool:
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT user_id, tariff FROM user_access WHERE expire_time <= %s", (current_time,))
                    return await cur.fetchall()

    async def save_user(self, user_id: int, username: Optional[str], first_name: Optional[str], last_name: Optional[str]):
        """Сохранение или обновление информации о пользователе."""
        async with self.create_pool() as pool:
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
                    """, (user_id, username, first_name, last_name))
        logger.debug(f"Сохранен пользователь {user_id}")

    async def get_all_users(self) -> List[int]:
        """Получение всех ID пользователей."""
        async with self.create_pool() as pool:
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT user_id FROM user_access")
                    rows = await cur.fetchall()
                    return [row[0] for row in rows]

    async def save_receipt(self, user_id: int, amount: float, check_number: str, fp: str, date_time: datetime, buyer_name: str, file_id: str) -> bool:
        """Сохранение данных чека в базе данных."""
        try:
            async with self.create_pool() as pool:
                async with pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        await cur.execute("""
                            INSERT INTO fiscal_checks 
                            (user_id, amount, check_number, fp, date_time, buyer_name, file_id)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (user_id, amount, check_number, fp, date_time, buyer_name, file_id))
                        return True
        except Exception as e:
            logger.error(f"Ошибка при сохранении чека для пользователя {user_id}: {e}")
            return False

    async def check_duplicate_file(self, file_id: str) -> bool:
        """Проверка, существует ли файл в базе данных."""
        async with self.create_pool() as pool:
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT 1 FROM fiscal_checks WHERE file_id = %s", (file_id,))
                    return await cur.fetchone() is not None

    async def parse_kaspi_receipt(self, pdf_path: str) -> Optional[dict]:
        """Парсинг чека Kaspi из PDF."""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                text = "\n".join(page.extract_text() for page in pdf.pages)
                
                data = {
                    "amount": float(re.search(r"(\d+)\s*₸", text).group(1)) if re.search(r"(\d+)\s*₸", text) else None,
                    "iin": re.search(r"ИИН/БИН продавца\s*(\d+)", text).group(1) if re.search(r"ИИН/БИН продавца\s*(\d+)", text) else None,
                    "check_number": re.search(r"№ чека\s*(\S+)", text).group(1) if re.search(r"№ чека\s*(\S+)", text) else None,
                    "fp": re.search(r"ФП\s*(\d+)", text).group(1) if re.search(r"ФП\s*(\d+)", text) else None,
                    "date_time": re.search(r"Дата и время\s*(?:по Астане)?\s*(\d{2}\.\d{2}\.\d{4} \d{2}:\d{2})", text).group(1) if re.search(r"Дата и время\s*(?:по Астане)?\s*(\d{2}\.\d{2}\.\d{4} \d{2}:\d{2})", text) else None,
                    "buyer_name": re.search(r"ФИО покупателя\s*(.+)", text).group(1).strip() if re.search(r"ФИО покупателя\s*(.+)", text) else None
                }
                # Удаление временного файла после обработки
                try:
                    os.remove(pdf_path)
                    logger.debug(f"Удален временный файл: {pdf_path}")
                except Exception as e:
                    logger.warning(f"Не удалось удалить временный файл {pdf_path}: {e}")
                return data
        except Exception as e:
            logger.error(f"Ошибка парсинга PDF чека: {e}")
            return None

    async def close(self):
        """Закрытие пула соединений с базой данных."""
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
            logger.info("Пул соединений с базой данных закрыт")
