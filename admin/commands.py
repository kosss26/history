"""
Админ-команды для управления ботом
"""
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from config import ADMIN_USER_IDS
from engine import story_engine
from storage.repository import RunRepository
from utils.logger import logger

router = Router(name="admin")

def is_admin(user_id: int) -> bool:
    """Проверить, является ли пользователь администратором"""
    return user_id in ADMIN_USER_IDS

@router.message(Command("start_story"))
async def cmd_start_story(message: Message):
    """Команда /start_story <story_id>"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещён. Только для администраторов.")
        return
    
    args = message.text.split()[1:] if message.text else []
    
    if len(args) < 1:
        await message.answer("❌ Использование: /start_story <story_id>")
        return
    
    story_id = args[0]
    user_id = message.from_user.id
    
    # Если указан user_id как второй аргумент, используем его
    if len(args) >= 2 and args[1].isdigit():
        user_id = int(args[1])
    
    result = await story_engine.start_story(user_id, story_id)
    
    if result is None:
        await message.answer(f"❌ Ошибка: история '{story_id}' не найдена или не может быть запущена.")
        return
    
    text, keyboard, run_id = result
    
    await message.answer(text, reply_markup=keyboard)
    logger.info(f"Админ {message.from_user.id} запустил историю {story_id} для пользователя {user_id}")

@router.message(Command("reset_story"))
async def cmd_reset_story(message: Message):
    """Команда /reset_story <user_id> <story_id>"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещён. Только для администраторов.")
        return
    
    args = message.text.split()[1:] if message.text else []
    
    if len(args) < 2:
        await message.answer("❌ Использование: /reset_story <user_id> <story_id>")
        return
    
    try:
        user_id = int(args[0])
        story_id = args[1]
    except ValueError:
        await message.answer("❌ Ошибка: user_id должен быть числом.")
        return
    
    await RunRepository.reset_run(user_id, story_id)
    await message.answer(f"✅ Попытка прохождения истории '{story_id}' для пользователя {user_id} сброшена.")
    logger.info(f"Админ {message.from_user.id} сбросил историю {story_id} для пользователя {user_id}")

@router.message(Command("preview_scene"))
async def cmd_preview_scene(message: Message):
    """Команда /preview_scene <story_id> <scene_id>"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещён. Только для администраторов.")
        return
    
    args = message.text.split()[1:] if message.text else []
    
    if len(args) < 2:
        await message.answer("❌ Использование: /preview_scene <story_id> <scene_id>")
        return
    
    story_id = args[0]
    scene_id = args[1]
    
    text = story_engine.preview_scene(story_id, scene_id)
    
    if text is None:
        await message.answer(f"❌ Сцена '{scene_id}' не найдена в истории '{story_id}'.")
        return
    
    await message.answer(f"📖 Предпросмотр сцены '{scene_id}':\n\n{text}")

@router.message(Command("active_runs"))
async def cmd_active_runs(message: Message):
    """Команда /active_runs - показать все активные попытки прохождения"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещён. Только для администраторов.")
        return
    
    runs = await RunRepository.get_all_active_runs()
    
    if not runs:
        await message.answer("📊 Активных попыток прохождения нет.")
        return
    
    lines = ["📊 Активные попытки прохождения:\n"]
    
    for run in runs:
        lines.append(
            f"• Run ID: {run.run_id}\n"
            f"  Пользователь: {run.user_id}\n"
            f"  История: {run.story_id}\n"
            f"  Сцена: {run.current_scene}\n"
            f"  Начато: {run.started_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        )
    
    text = "\n".join(lines)
    
    # Telegram ограничивает длину сообщения, разбиваем если нужно
    if len(text) > 4096:
        chunks = [text[i:i+4096] for i in range(0, len(text), 4096)]
        for chunk in chunks:
            await message.answer(chunk)
    else:
        await message.answer(text)
