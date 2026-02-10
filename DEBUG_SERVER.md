# Отладка на сервере

## Проверка логов

```bash
# Посмотреть последние 50 строк логов
journalctl -u storybot -n 50 --no-pager

# Смотреть логи в реальном времени
journalctl -u storybot -f
```

## Возможные проблемы

### 1. BOT_TOKEN не установлен
**Симптом**: `BOT_TOKEN не установлен!`

**Решение**:
```bash
# Проверить .env файл
cat /root/apps/story-quest-bot/.env

# Если файла нет, создать:
cat > /root/apps/story-quest-bot/.env << 'EOF'
BOT_TOKEN=8288514510:AAG-9ZZdOqI6FbPAgtzWcK2jA-cIUbHCAks
ADMIN_USER_IDS=1763619724
DEBUG=False
DB_PATH=bot.db
STORIES_DIR=stories
EOF
```

### 2. Ошибка импорта модулей
**Симптом**: `ModuleNotFoundError` или `ImportError`

**Решение**:
```bash
# Проверить, что виртуальное окружение активировано
cd /root/apps/story-quest-bot
source .venv/bin/activate

# Переустановить зависимости
pip install -r requirements.txt

# Проверить импорты вручную
python3 -c "from bot import bot; print('OK')"
```

### 3. Ошибка подключения к БД
**Симптом**: `Ошибка подключения к БД`

**Решение**:
```bash
# Проверить права на файл БД
ls -la /root/apps/story-quest-bot/bot.db

# Если файла нет, он создастся автоматически
# Проверить права на директорию
ls -la /root/apps/story-quest-bot/
```

### 4. Ошибка загрузки историй
**Симптом**: `Директория историй не найдена`

**Решение**:
```bash
# Проверить наличие директории stories
ls -la /root/apps/story-quest-bot/stories/

# Если нет, создать и скопировать истории
mkdir -p /root/apps/story-quest-bot/stories
# Скопировать истории из репозитория
```

## Ручной запуск для отладки

```bash
cd /root/apps/story-quest-bot
source .venv/bin/activate
python3 bot.py
```

Это покажет ошибки напрямую в консоли.

## Проверка конфигурации systemd

```bash
# Проверить unit-файл
cat /etc/systemd/system/storybot.service

# Проверить пути в unit-файле
# Должны совпадать с реальными путями:
# - WorkingDirectory
# - EnvironmentFile
# - ExecStart
```

## Быстрая диагностика

```bash
# 1. Проверить .env
cat /root/apps/story-quest-bot/.env

# 2. Проверить Python и зависимости
cd /root/apps/story-quest-bot
source .venv/bin/activate
python3 --version
pip list | grep aiogram

# 3. Попробовать импортировать модули
python3 -c "import sys; sys.path.insert(0, '.'); from config import BOT_TOKEN; print('BOT_TOKEN:', 'OK' if BOT_TOKEN else 'EMPTY')"

# 4. Проверить логи
journalctl -u storybot -n 50 --no-pager
```
