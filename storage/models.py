"""
Модели данных
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any

@dataclass
class User:
    """Модель пользователя"""
    user_id: int
    username: Optional[str]
    created_at: datetime

@dataclass
class Run:
    """Модель попытки прохождения истории"""
    run_id: int
    user_id: int
    story_id: str
    current_scene: str
    is_finished: bool
    started_at: datetime
    finished_at: Optional[datetime] = None

@dataclass
class Flag:
    """Модель флага"""
    run_id: int
    flag_name: str
    flag_value: str
