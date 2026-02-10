"""
Репозиторий для работы с данными
"""
from typing import Optional, List, Dict
from datetime import datetime
from storage.db import db
from storage.models import User, Run, Flag
from utils.logger import logger

class UserRepository:
    """Репозиторий для работы с пользователями"""
    
    @staticmethod
    async def get_or_create(user_id: int, username: Optional[str] = None) -> User:
        """Получить или создать пользователя"""
        async with db.connection.execute(
            "SELECT * FROM users WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            
            if row:
                return User(
                    user_id=row["user_id"],
                    username=row["username"],
                    created_at=datetime.fromisoformat(row["created_at"])
                )
        
        # Создаём нового пользователя
        async with db.connection.execute(
            "INSERT INTO users (user_id, username) VALUES (?, ?)",
            (user_id, username)
        ) as cursor:
            await db.connection.commit()
        
        return User(
            user_id=user_id,
            username=username,
            created_at=datetime.now()
        )

class RunRepository:
    """Репозиторий для работы с попытками прохождения"""
    
    @staticmethod
    async def create(user_id: int, story_id: str, start_scene: str) -> Run:
        """Создать новую попытку прохождения"""
        async with db.connection.execute(
            """INSERT INTO runs (user_id, story_id, current_scene, is_finished)
               VALUES (?, ?, ?, 0)""",
            (user_id, story_id, start_scene)
        ) as cursor:
            await db.connection.commit()
            run_id = cursor.lastrowid
        
        async with db.connection.execute(
            "SELECT * FROM runs WHERE run_id = ?",
            (run_id,)
        ) as cursor:
            row = await cursor.fetchone()
        
        return Run(
            run_id=row["run_id"],
            user_id=row["user_id"],
            story_id=row["story_id"],
            current_scene=row["current_scene"],
            is_finished=bool(row["is_finished"]),
            started_at=datetime.fromisoformat(row["started_at"]),
            finished_at=datetime.fromisoformat(row["finished_at"]) if row["finished_at"] else None
        )
    
    @staticmethod
    async def get_active_run(user_id: int, story_id: str) -> Optional[Run]:
        """Получить активную попытку прохождения"""
        async with db.connection.execute(
            """SELECT * FROM runs 
               WHERE user_id = ? AND story_id = ? AND is_finished = 0
               ORDER BY started_at DESC LIMIT 1""",
            (user_id, story_id)
        ) as cursor:
            row = await cursor.fetchone()
            
            if not row:
                return None
            
            return Run(
                run_id=row["run_id"],
                user_id=row["user_id"],
                story_id=row["story_id"],
                current_scene=row["current_scene"],
                is_finished=bool(row["is_finished"]),
                started_at=datetime.fromisoformat(row["started_at"]),
                finished_at=datetime.fromisoformat(row["finished_at"]) if row["finished_at"] else None
            )
    
    @staticmethod
    async def update_scene(run_id: int, scene_id: str):
        """Обновить текущую сцену"""
        async with db.connection.execute(
            "UPDATE runs SET current_scene = ? WHERE run_id = ?",
            (scene_id, run_id)
        ) as cursor:
            await db.connection.commit()
    
    @staticmethod
    async def finish_run(run_id: int):
        """Завершить попытку прохождения"""
        async with db.connection.execute(
            """UPDATE runs 
               SET is_finished = 1, finished_at = CURRENT_TIMESTAMP 
               WHERE run_id = ?""",
            (run_id,)
        ) as cursor:
            await db.connection.commit()
    
    @staticmethod
    async def get_all_active_runs() -> List[Run]:
        """Получить все активные попытки прохождения"""
        async with db.connection.execute(
            "SELECT * FROM runs WHERE is_finished = 0 ORDER BY started_at DESC"
        ) as cursor:
            rows = await cursor.fetchall()
        
        return [
            Run(
                run_id=row["run_id"],
                user_id=row["user_id"],
                story_id=row["story_id"],
                current_scene=row["current_scene"],
                is_finished=bool(row["is_finished"]),
                started_at=datetime.fromisoformat(row["started_at"]),
                finished_at=datetime.fromisoformat(row["finished_at"]) if row["finished_at"] else None
            )
            for row in rows
        ]
    
    @staticmethod
    async def reset_run(user_id: int, story_id: str):
        """Сбросить попытку прохождения (удалить активную)"""
        # Удаляем флаги
        async with db.connection.execute(
            """DELETE FROM flags 
               WHERE run_id IN (
                   SELECT run_id FROM runs 
                   WHERE user_id = ? AND story_id = ? AND is_finished = 0
               )""",
            (user_id, story_id)
        ) as cursor:
            await db.connection.commit()
        
        # Удаляем попытку
        async with db.connection.execute(
            """DELETE FROM runs 
               WHERE user_id = ? AND story_id = ? AND is_finished = 0""",
            (user_id, story_id)
        ) as cursor:
            await db.connection.commit()
    
    @staticmethod
    async def _get_run_by_id(run_id: int) -> Optional[Run]:
        """Получить попытку прохождения по ID"""
        async with db.connection.execute(
            "SELECT * FROM runs WHERE run_id = ?",
            (run_id,)
        ) as cursor:
            row = await cursor.fetchone()
            
            if not row:
                return None
            
            return Run(
                run_id=row["run_id"],
                user_id=row["user_id"],
                story_id=row["story_id"],
                current_scene=row["current_scene"],
                is_finished=bool(row["is_finished"]),
                started_at=datetime.fromisoformat(row["started_at"]),
                finished_at=datetime.fromisoformat(row["finished_at"]) if row["finished_at"] else None
            )

class FlagRepository:
    """Репозиторий для работы с флагами"""
    
    @staticmethod
    async def get_flags(run_id: int) -> Dict[str, str]:
        """Получить все флаги для попытки прохождения"""
        async with db.connection.execute(
            "SELECT flag_name, flag_value FROM flags WHERE run_id = ?",
            (run_id,)
        ) as cursor:
            rows = await cursor.fetchall()
        
        return {row["flag_name"]: row["flag_value"] for row in rows}
    
    @staticmethod
    async def set_flag(run_id: int, flag_name: str, flag_value: str):
        """Установить флаг"""
        async with db.connection.execute(
            """INSERT OR REPLACE INTO flags (run_id, flag_name, flag_value)
               VALUES (?, ?, ?)""",
            (run_id, flag_name, flag_value)
        ) as cursor:
            await db.connection.commit()
    
    @staticmethod
    async def remove_flag(run_id: int, flag_name: str):
        """Удалить флаг"""
        async with db.connection.execute(
            "DELETE FROM flags WHERE run_id = ? AND flag_name = ?",
            (run_id, flag_name)
        ) as cursor:
            await db.connection.commit()
    
    @staticmethod
    async def has_flag(run_id: int, flag_name: str) -> bool:
        """Проверить наличие флага"""
        async with db.connection.execute(
            "SELECT 1 FROM flags WHERE run_id = ? AND flag_name = ? LIMIT 1",
            (run_id, flag_name)
        ) as cursor:
            row = await cursor.fetchone()
            return row is not None
