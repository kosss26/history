"""
Обработчики главного меню и выбора историй
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, StateFilter
from engine import story_engine
from storage.repository import UserRepository, RunRepository
from config import DEBUG
from utils.logger import logger

router = Router(name="menu")

# Главная клавиатура
def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Создать главную клавиатуру"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📚 Истории")],
            [KeyboardButton(text="ℹ️ Помощь"), KeyboardButton(text="🔄 Начать заново")]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_stories_inline_keyboard() -> InlineKeyboardMarkup:
    """Создать inline-клавиатуру со списком историй"""
    stories = story_engine.list_stories()
    
    buttons = []
    for story_id, story_data in stories.items():
        title = story_data.get("title", story_id)
        version = story_data.get("version", "1.0")
        button_text = f"{title} — v{version}"
        
        buttons.append([
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"story_select:{story_id}"
            )
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@router.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    user = await UserRepository.get_or_create(
        message.from_user.id,
        message.from_user.username
    )
    
    welcome_text = (
        "👋 Привет! Я бот интерактивных историй.\n"
        "Выбирай сюжет, принимай решения — и смотри, к чему они приведут."
    )
    
    await message.answer(
        welcome_text,
        reply_markup=get_main_keyboard()
    )

@router.message(F.text == "📚 Истории")
async def show_stories(message: Message):
    """Показать список историй"""
    stories = story_engine.list_stories()
    
    if not stories:
        await message.answer(
            "📚 Истории пока не загружены.\n"
            "Попробуй позже или обратись к администратору.",
            reply_markup=get_main_keyboard()
        )
        return
    
    text = "📚 Доступные истории:\nВыбери одну, чтобы начать."
    
    keyboard = get_stories_inline_keyboard()
    await message.answer(text, reply_markup=keyboard)

@router.message(F.text == "ℹ️ Помощь")
async def show_help(message: Message):
    """Показать справку"""
    help_text = (
        "ℹ️ Как играть:\n\n"
        "1. Нажми «📚 Истории» и выбери сюжет\n"
        "2. Читай текст и принимай решения\n"
        "3. Твой выбор влияет на развитие сюжета\n"
        "4. Дойди до финала и узнай, к чему привели твои решения\n\n"
        "💡 Совет: некоторые выборы могут быть доступны только при определённых условиях."
    )
    
    await message.answer(help_text, reply_markup=get_main_keyboard())

@router.message(F.text == "🔄 Начать заново")
async def reset_progress(message: Message):
    """Сброс прогресса с подтверждением"""
    user_id = message.from_user.id
    
    # Получаем все активные попытки пользователя
    all_runs = await RunRepository.get_all_active_runs()
    user_runs = [r for r in all_runs if r.user_id == user_id]
    
    if not user_runs:
        await message.answer(
            "✅ У тебя нет активных попыток прохождения.\n"
            "Выбери историю через кнопку «📚 Истории».",
            reply_markup=get_main_keyboard()
        )
        return
    
    # Показываем список активных историй для сброса
    if len(user_runs) == 1:
        # Одна активная история - сразу предлагаем сбросить
        run = user_runs[0]
        story = story_engine.get_story(run.story_id)
        title = story.get("title", run.story_id) if story else run.story_id
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, сбросить", callback_data=f"reset_confirm:{run.story_id}"),
                InlineKeyboardButton(text="❌ Нет, отменить", callback_data="reset_cancel")
            ]
        ])
        
        await message.answer(
            f"⚠️ Сбросить прогресс по истории «{title}»?\n"
            f"Твой текущий прогресс будет потерян.",
            reply_markup=keyboard
        )
    else:
        # Несколько активных историй - показываем список
        buttons = []
        for run in user_runs:
            story = story_engine.get_story(run.story_id)
            title = story.get("title", run.story_id) if story else run.story_id
            buttons.append([
                InlineKeyboardButton(
                    text=f"🔄 {title}",
                    callback_data=f"reset_select:{run.story_id}"
                )
            ])
        
        buttons.append([
            InlineKeyboardButton(text="❌ Отменить", callback_data="reset_cancel")
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        await message.answer(
            "🔄 Выбери историю для сброса прогресса:",
            reply_markup=keyboard
        )

@router.callback_query(F.data.startswith("story_select:"))
async def process_story_selection(callback: CallbackQuery):
    """Обработка выбора истории"""
    story_id = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id
    
    # Получаем или создаём пользователя
    await UserRepository.get_or_create(
        user_id,
        callback.from_user.username
    )
    
    story = story_engine.get_story(story_id)
    if not story:
        await callback.answer("❌ История не найдена", show_alert=True)
        await callback.message.edit_text(
            "❌ История не найдена.\nВыбери другую историю.",
            reply_markup=get_stories_inline_keyboard()
        )
        return
    
    # Проверяем активную попытку
    active_run = await RunRepository.get_active_run(user_id, story_id)
    
    if active_run:
        # Продолжаем существующую попытку
        result = await story_engine.continue_story(active_run.run_id)
        if result:
            text, keyboard, run_id = result
            
            # Убираем клавиатуру выбора историй
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer()
            return
    
    # Проверяем, была ли завершённая попытка
    allow_restart = story.get("allow_restart", False)
    
    # Проверяем завершённые попытки
    from storage.db import db
    from datetime import datetime
    
    if db.connection:
        async with db.connection.execute(
            """SELECT * FROM runs 
               WHERE user_id = ? AND story_id = ? AND is_finished = 1
               ORDER BY finished_at DESC LIMIT 1""",
            (user_id, story_id)
        ) as cursor:
            row = await cursor.fetchone()
            has_finished = row is not None
    else:
        has_finished = False
    
    # Если есть завершённая попытка и allow_restart=false
    if has_finished and not allow_restart:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📚 Выбрать другую историю", callback_data="show_stories")]
        ])
        
        title = story.get("title", story_id)
        await callback.message.edit_text(
            f"❌ История «{title}» завершена и недоступна для повторного прохождения.\n"
            f"Выбери другую историю.",
            reply_markup=keyboard
        )
        await callback.answer()
        return
    
    # Если есть завершённая попытка и allow_restart=true - предлагаем начать заново
    if has_finished and allow_restart:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="▶️ Начать заново", callback_data=f"story_restart:{story_id}"),
                InlineKeyboardButton(text="↩️ Вернуться к списку", callback_data="show_stories")
            ]
        ])
        
        title = story.get("title", story_id)
        await callback.message.edit_text(
            f"📖 История «{title}» уже завершена.\n"
            f"Хочешь начать заново?",
            reply_markup=keyboard
        )
        await callback.answer()
        return
    
    # Запускаем новую попытку
    result = await story_engine.start_story(user_id, story_id)
    
    if result is None:
        # Неожиданная ошибка
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📚 Выбрать другую историю", callback_data="show_stories")]
        ])
        
        await callback.message.edit_text(
            "❌ Ошибка запуска истории.\n"
            "Попробуй выбрать другую историю.",
            reply_markup=keyboard
        )
        await callback.answer("❌ Ошибка запуска", show_alert=True)
        return
    
    text, keyboard, run_id = result
    
    # Убираем клавиатуру выбора историй и показываем первую сцену
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()
    
    logger.info(f"Пользователь {user_id} запустил историю {story_id} (run_id: {run_id})")

@router.callback_query(F.data.startswith("story_restart:"))
async def restart_story(callback: CallbackQuery):
    """Перезапуск истории"""
    story_id = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id
    
    # Сбрасываем активную попытку, если есть
    await RunRepository.reset_run(user_id, story_id)
    
    # Запускаем новую попытку
    result = await story_engine.start_story(user_id, story_id)
    
    if result:
        text, keyboard, run_id = result
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer("✅ История перезапущена")
    else:
        await callback.answer("❌ Ошибка перезапуска", show_alert=True)

@router.callback_query(F.data == "show_stories")
async def show_stories_callback(callback: CallbackQuery):
    """Показать список историй через callback"""
    stories = story_engine.list_stories()
    
    if not stories:
        await callback.message.edit_text(
            "📚 Истории пока не загружены.",
            reply_markup=None
        )
        await callback.answer()
        return
    
    text = "📚 Доступные истории:\nВыбери одну, чтобы начать."
    keyboard = get_stories_inline_keyboard()
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("reset_select:"))
async def reset_select_story(callback: CallbackQuery):
    """Выбор истории для сброса"""
    story_id = callback.data.split(":", 1)[1]
    
    story = story_engine.get_story(story_id)
    title = story.get("title", story_id) if story else story_id
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, сбросить", callback_data=f"reset_confirm:{story_id}"),
            InlineKeyboardButton(text="❌ Нет, отменить", callback_data="reset_cancel")
        ]
    ])
    
    await callback.message.edit_text(
        f"⚠️ Сбросить прогресс по истории «{title}»?\n"
        f"Твой текущий прогресс будет потерян.",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data.startswith("reset_confirm:"))
async def reset_confirm(callback: CallbackQuery):
    """Подтверждение сброса прогресса"""
    story_id = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id
    
    await RunRepository.reset_run(user_id, story_id)
    
    story = story_engine.get_story(story_id)
    title = story.get("title", story_id) if story else story_id
    
    await callback.message.edit_text(
        f"✅ Прогресс по истории «{title}» сброшен.\n"
        f"Можешь начать заново через кнопку «📚 Истории»."
    )
    await callback.answer("✅ Прогресс сброшен")

@router.callback_query(F.data == "reset_cancel")
async def reset_cancel(callback: CallbackQuery):
    """Отмена сброса"""
    await callback.message.edit_text("❌ Сброс отменён.")
    await callback.answer()
