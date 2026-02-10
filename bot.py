"""
Основной файл Telegram-бота с narrative engine
"""
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, DEBUG, ADMIN_USER_IDS
from storage.db import db
from storage.repository import UserRepository
from engine import story_engine
from admin.commands import router as admin_router
from admin.editor import router as admin_editor_router
from handlers.menu import router as menu_router
from utils.logger import logger

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Регистрация роутеров (порядок важен - более специфичные первыми)
dp.include_router(menu_router)  # Главное меню и выбор историй
dp.include_router(admin_router)  # Админ-команды
dp.include_router(admin_editor_router)  # Расширенные админ-команды

class StoryStates(StatesGroup):
    """Состояния для FSM (пока не используется, но может пригодиться)"""
    pass

@dp.message(Command("play"))
async def cmd_play(message: Message):
    """Обработчик команды /play - только для админов или скрыта"""
    user_id = message.from_user.id
    
    # Для админов - можно использовать старый формат
    if user_id in ADMIN_USER_IDS or DEBUG:
        args = message.text.split()[1:] if message.text else []
        
        if len(args) < 1:
            await message.answer("❌ Использование: /play <story_id>")
            return
        
        story_id = args[0]
        
        # Получаем или создаём пользователя
        await UserRepository.get_or_create(
            user_id,
            message.from_user.username
        )
        
        # Запускаем историю
        result = await story_engine.start_story(user_id, story_id)
        
        if result is None:
            await message.answer(
                f"❌ Ошибка: история '{story_id}' не найдена или уже запущена."
            )
            return
        
        text, keyboard, run_id = result
        await message.answer(text, reply_markup=keyboard)
        logger.info(f"Админ {user_id} запустил историю {story_id} (run_id: {run_id})")
    else:
        # Для обычных пользователей - показываем подсказку
        await message.answer(
            "💡 Выбери историю через кнопку «📚 Истории» в меню."
        )

@dp.message(Command("list"))
async def cmd_list(message: Message):
    """Обработчик команды /list - для обычных пользователей показывает подсказку"""
    user_id = message.from_user.id
    
    # Для админов - показываем полный список
    if user_id in ADMIN_USER_IDS or DEBUG:
        stories = story_engine.list_stories()
        
        if not stories:
            await message.answer("📚 Истории не найдены.")
            return
        
        lines = ["📚 Доступные истории:\n"]
        
        for story_id, story_data in stories.items():
            title = story_data.get("title", story_id)
            description = story_data.get("description", "")
            version = story_data.get("version", "1.0")
            
            lines.append(f"• {title}")
            lines.append(f"  ID: {story_id}")
            if description:
                lines.append(f"  {description}")
            lines.append(f"  Версия: {version}")
            lines.append("")
        
        text = "\n".join(lines)
        
        # Telegram ограничивает длину сообщения
        if len(text) > 4096:
            chunks = [text[i:i+4096] for i in range(0, len(text), 4096)]
            for chunk in chunks:
                await message.answer(chunk)
        else:
            await message.answer(text)
    else:
        # Для обычных пользователей - короткая подсказка
        await message.answer(
            "💡 Открой меню → 📚 Истории"
        )

@dp.callback_query(F.data.startswith("choice:"))
async def process_choice(callback: CallbackQuery):
    """Обработчик выбора игрока"""
    # Формат callback_data: choice:<run_id>:<scene_id>:<choice_id>
    parts = callback.data.split(":")
    
    if len(parts) != 4:
        await callback.answer("❌ Ошибка обработки выбора", show_alert=True)
        return
    
    _, run_id_str, scene_id, choice_id = parts
    
    try:
        run_id = int(run_id_str)
    except ValueError:
        await callback.answer("❌ Ошибка: неверный run_id", show_alert=True)
        return
    
    user_id = callback.from_user.id
    
    # Проверяем, что попытка принадлежит пользователю
    from storage.repository import RunRepository
    run = await RunRepository._get_run_by_id(run_id)
    
    if not run:
        await callback.answer("❌ Попытка прохождения не найдена", show_alert=True)
        await callback.message.edit_text("❌ Ошибка: попытка прохождения не найдена.")
        return
    
    if run.user_id != user_id:
        await callback.answer("❌ Эта попытка принадлежит другому пользователю", show_alert=True)
        return
    
    if run.is_finished:
        await callback.answer("❌ Эта история уже завершена", show_alert=True)
        return
    
    # Проверяем, что сцена совпадает
    if run.current_scene != scene_id:
        await callback.answer("❌ Сцена уже изменилась", show_alert=True)
        # Обновляем сообщение текущей сценой
        result = await story_engine.continue_story(run_id)
        if result:
            text, keyboard, _ = result
            await callback.message.edit_text(text, reply_markup=keyboard)
        return
    
    # Обрабатываем выбор
    result = await story_engine.process_choice(run_id, scene_id, choice_id)
    
    if result is None:
        await callback.answer("❌ Ошибка обработки выбора (возможно, условие не выполнено)", show_alert=True)
        return
    
    text, keyboard, run_id = result
    
    # Если история завершена (keyboard is None), добавляем кнопку возврата в меню
    if keyboard is None:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📚 Выбрать другую историю", callback_data="show_stories")]
        ])
    
    # Удаляем кнопки и обновляем сообщение
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()
    
    logger.info(f"Пользователь {user_id} сделал выбор {choice_id} в сцене {scene_id} (run_id: {run_id})")

async def on_startup():
    """Действия при запуске бота"""
    logger.info("Запуск бота...")
    await db.connect()
    logger.info("Бот запущен")

async def on_shutdown():
    """Действия при остановке бота"""
    logger.info("Остановка бота...")
    await db.disconnect()
    logger.info("Бот остановлен")

async def main():
    """Главная функция"""
    # Регистрируем обработчики запуска и остановки
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    # Запускаем бота
    logger.info("Запуск polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
