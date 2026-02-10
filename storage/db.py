"""
Инициализация и управление базой данных SQLite
"""
import aiosqlite
from typing import Optional
from config import DB_PATH
from utils.logger import logger

class Database:
    """Класс для работы с базой данных"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.connection: Optional[aiosqlite.Connection] = None
    
    async def connect(self):
        """Подключение к базе данных"""
        self.connection = await aiosqlite.connect(self.db_path)
        self.connection.row_factory = aiosqlite.Row
        await self.init_tables()
        logger.info(f"Подключено к БД: {self.db_path}")
    
    async def disconnect(self):
        """Отключение от базы данных"""
        if self.connection:
            await self.connection.close()
            logger.info("Отключено от БД")
    
    async def init_tables(self):
        """Инициализация таблиц"""
        async with self.connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """) as cursor:
            await self.connection.commit()
        
        async with self.connection.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                story_id TEXT NOT NULL,
                current_scene TEXT NOT NULL,
                is_finished INTEGER DEFAULT 0,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                finished_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """) as cursor:
            await self.connection.commit()
        
        async with self.connection.execute("""
            CREATE TABLE IF NOT EXISTS flags (
                run_id INTEGER NOT NULL,
                flag_name TEXT NOT NULL,
                flag_value TEXT NOT NULL,
                PRIMARY KEY (run_id, flag_name),
                FOREIGN KEY (run_id) REFERENCES runs(run_id)
            )
        """) as cursor:
            await self.connection.commit()
        
        # Индексы для оптимизации
        async with self.connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_runs_user_story 
            ON runs(user_id, story_id, is_finished)
        """) as cursor:
            await self.connection.commit()
        
        async with self.connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_flags_run 
            ON flags(run_id)
        """) as cursor:
            await self.connection.commit()
        
        logger.info("Таблицы БД инициализированы")

# Глобальный экземпляр БД
db = Database()
