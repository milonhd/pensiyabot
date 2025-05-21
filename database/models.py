"""
Модуль содержит SQL-скрипты для создания таблиц в базе данных
"""

# SQL для создания таблицы пользовательских доступов
CREATE_USER_ACCESS_TABLE = """
CREATE TABLE IF NOT EXISTS user_access (
    user_id BIGINT PRIMARY KEY,
    expire_time BIGINT,
    tariff VARCHAR(20),
    username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    joined_at TIMESTAMP DEFAULT NOW()
)
"""

# SQL для создания таблицы фискальных чеков
CREATE_FISCAL_CHECKS_TABLE = """
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
"""
