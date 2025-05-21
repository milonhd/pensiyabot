from pydantic_settings import BaseSettings
import os
from dotenv import load_dotenv

load_dotenv()

class Config(BaseSettings):
    api_token: str
    database_url: str
    admin_id: int
    receipt_dir: str = "/app/receipts"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def __init__(self):
        super().__init__()
        if not self.api_token or not self.database_url or not self.admin_id:
            raise ValueError("Не заданы обязательные переменные окружения: API_TOKEN, DATABASE_URL, ADMIN_ID")
