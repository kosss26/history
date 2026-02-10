"""
Основной файл Telegram-бота с narrative engine
"""
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
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
    
    # ВСЕГДА вызываем answer() как можно раньше для мгновенной реакции
    await callback.answer()
    
    # Проверяем, что попытка принадлежит пользователю
    from storage.repository import RunRepository
    from aiogram.types import ReplyKeyboardRemove
    
    try:
        run = await RunRepository._get_run_by_id(run_id)
        
        if not run:
            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.message.answer("❌ Ошибка: попытка прохождения не найдена.")
            return
        
        if run.user_id != user_id:
            await callback.message.edit_reply_markup(reply_markup=None)
            return
        
        # Повторное нажатие - без alert, просто выходим
        if run.is_finished:
            await callback.message.edit_reply_markup(reply_markup=None)
            return
        
        # Проверяем, что сцена совпадает
        if run.current_scene != scene_id:
            # Обновляем сообщение текущей сценой
            result = await story_engine.continue_story(run_id)
            if result:
                text, keyboard, _ = result
                await callback.message.edit_reply_markup(reply_markup=None)
                await callback.message.edit_text(text, reply_markup=keyboard)
            return
        
        # Обрабатываем выбор
        result = await story_engine.process_choice(run_id, scene_id, choice_id)
        
        if result is None:
            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.message.answer("❌ Ошибка обработки выбора (возможно, условие не выполнено).")
            return
        
        text, keyboard, new_run_id = result
        
        # ВСЕГДА убираем кнопки у сообщения сцены
        await callback.message.edit_reply_markup(reply_markup=None)
        
        # Проверяем, это финал?
        run_after = await RunRepository._get_run_by_id(new_run_id)
        is_finished = run_after and run_after.is_finished
        
        if is_finished:
            # Это финал - отправляем НОВОЕ сообщение
            from utils.ui_texts import get_ending_header, get_ending_keyboard
            
            story = story_engine.get_story(run_after.story_id)
            if story:
                endings = story.get("endings", {})
                ending = endings.get(run_after.current_scene, {})
                ending_type = ending.get("ending_type", "neutral")
                
                header = get_ending_header(ending_type)
                allow_restart = story.get("allow_restart", False)
                
                formatted_text = f"{header}\n\n{text}"
                ending_keyboard = get_ending_keyboard(run_after.story_id, allow_restart)
            else:
                # История не найдена, но финал есть
                formatted_text = f"🏁 Финал\n\n{text}"
                ending_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📚 Другие истории", callback_data="show_stories:0")],
                    [InlineKeyboardButton(text="🏠 Меню", callback_data="service_menu")]
                ])
            
            # Отправляем новое сообщение с финалом и сворачиваем ReplyKeyboard
            await callback.message.answer(
                formatted_text,
                reply_markup=ending_keyboard
            )
        else:
            # Обычная сцена - обновляем сообщение БЕЗ сервисных кнопок
            await callback.message.edit_text(text, reply_markup=keyboard)
        
        logger.info(f"Пользователь {user_id} сделал выбор {choice_id} в сцене {scene_id} (run_id: {new_run_id})")
    
    except Exception as e:
        logger.error(f"Ошибка при обработке выбора: {e}", exc_info=True)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("❌ Произошла ошибка. Попробуй выбрать другую историю.")

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
