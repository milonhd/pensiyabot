from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, BigInteger

# 👇 вставь свою ссылку от Railway сюда
DATABASE_URL = "postgresql://postgres:EAppTZSxGhfhXhMMuoaEjvBZRRLbgdNw@postgres.railway.internal:5432/railway"

engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

class Access(Base):
    __tablename__ = "access"
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, unique=True)

# функция для создания таблиц (запускай один раз)
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
