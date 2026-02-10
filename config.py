"""
Конфигурация бота
"""
import os
from typing import List

# Telegram Bot Token
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "8288514510:AAG-9ZZdOqI6FbPAgtzWcK2jA-cIUbHCAks")

# ID администраторов (список)
ADMIN_USER_IDS: List[int] = [
    int(uid) for uid in os.getenv("ADMIN_USER_IDS", "1763619724").split(",") if uid.strip().isdigit()
]

# Режим отладки
DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"

# Путь к базе данных
DB_PATH: str = os.getenv("DB_PATH", "bot.db")

# Путь к директории с историями
STORIES_DIR: str = os.getenv("STORIES_DIR", "stories")
