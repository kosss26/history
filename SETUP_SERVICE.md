# Настройка бота как systemd сервиса

## Шаг 1: Скопировать unit-файл на сервер

```bash
# На вашем локальном компьютере (Mac) файл уже создан: storybot.service
# Скопируйте его на сервер:

scp storybot.service root@91.218.115.167:/etc/systemd/system/storybot.service
```

## Шаг 2: На сервере - отредактировать пути (если нужно)

```bash
# Если проект в другом месте или другой пользователь, отредактируйте:
sudo nano /etc/systemd/system/storybot.service

# Измените пути:
# - User=root (или другой пользователь)
# - WorkingDirectory=/root/apps/story-quest-bot (ваш путь)
# - EnvironmentFile=/root/apps/story-quest-bot/.env
# - ExecStart=/root/apps/story-quest-bot/.venv/bin/python /root/apps/story-quest-bot/bot.py
```

## Шаг 3: Создать .env файл на сервере

```bash
cd /root/apps/story-quest-bot
nano .env
```

Вставьте:
```
BOT_TOKEN=8288514510:AAG-9ZZdOqI6FbPAgtzWcK2jA-cIUbHCAks
ADMIN_USER_IDS=1763619724
DEBUG=False
DB_PATH=bot.db
STORIES_DIR=stories
```

## Шаг 4: Активировать и запустить сервис

```bash
# Перезагрузить systemd
sudo systemctl daemon-reload

# Включить автозапуск при загрузке системы
sudo systemctl enable storybot

# Запустить сервис
sudo systemctl start storybot

# Проверить статус
sudo systemctl status storybot
```

## Шаг 5: Просмотр логов

```bash
# Просмотр логов в реальном времени
journalctl -u storybot -f

# Просмотр последних 100 строк
journalctl -u storybot -n 100

# Просмотр логов за сегодня
journalctl -u storybot --since today
```

## Управление сервисом

```bash
# Остановить
sudo systemctl stop storybot

# Запустить
sudo systemctl start storybot

# Перезапустить
sudo systemctl restart storybot

# Проверить статус
sudo systemctl status storybot

# Отключить автозапуск
sudo systemctl disable storybot
```

## Если используете отдельного пользователя (рекомендуется)

Если хотите запускать от имени отдельного пользователя (безопаснее):

```bash
# Создать пользователя
sudo useradd -m -s /bin/bash storybot

# Переместить проект
sudo mv /root/apps/story-quest-bot /home/storybot/apps/

# Изменить владельца
sudo chown -R storybot:storybot /home/storybot/apps/story-quest-bot

# В unit-файле изменить:
# User=storybot
# WorkingDirectory=/home/storybot/apps/story-quest-bot
# EnvironmentFile=/home/storybot/apps/story-quest-bot/.env
# ExecStart=/home/storybot/apps/story-quest-bot/.venv/bin/python /home/storybot/apps/story-quest-bot/bot.py
```

## Проверка работы

После запуска проверьте:
1. Статус: `sudo systemctl status storybot` - должен быть "active (running)"
2. Логи: `journalctl -u storybot -f` - не должно быть ошибок
3. Бот отвечает в Telegram

## Устранение проблем

Если сервис не запускается:

```bash
# Проверить логи ошибок
journalctl -u storybot -n 50

# Проверить права на файлы
ls -la /root/apps/story-quest-bot/.env
ls -la /root/apps/story-quest-bot/.venv/bin/python

# Проверить, что .env файл существует и читается
cat /root/apps/story-quest-bot/.env

# Проверить, что Python работает
/root/apps/story-quest-bot/.venv/bin/python --version
```
