"""
Обработчики главного меню и выбора историй
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, StateFilter
from engine import story_engine
from storage.repository import UserRepository, RunRepository
from utils.ui_texts import *
from utils.logger import logger

router = Router(name="menu")

# Главная клавиатура
def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Создать главную клавиатуру"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📚 Истории")],
            [KeyboardButton(text="🧭 Продолжить"), KeyboardButton(text="🔄 Новая попытка")],
            [KeyboardButton(text="ℹ️ Помощь")]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_stories_inline_keyboard(page: int = 0, per_page: int = 10) -> tuple[InlineKeyboardMarkup, int]:
    """Создать inline-клавиатуру со списком историй с пагинацией"""
    stories = story_engine.list_stories()
    story_list = list(stories.items())
    total_pages = (len(story_list) + per_page - 1) // per_page
    
    if page < 0:
        page = 0
    if page >= total_pages:
        page = max(0, total_pages - 1)
    
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_stories = story_list[start_idx:end_idx]
    
    buttons = []
    for story_id, story_data in page_stories:
        title = story_data.get("title", story_id)
        version = story_data.get("version", "1.0")
        button_text = f"{title} · v{version}"
        
        buttons.append([
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"story_select:{story_id}"
            )
        ])
    
    # Пагинация
    nav_buttons = []
    if total_pages > 1:
        if page > 0:
            nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"story_page:{page-1}"))
        
        nav_buttons.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="story_page_info"))
        
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"story_page:{page+1}"))
        
        if nav_buttons:
            buttons.append(nav_buttons)
    
    return InlineKeyboardMarkup(inline_keyboard=buttons), total_pages

def get_story_card_keyboard(story_id: str, user_id: int, has_active_run: bool, allow_restart: bool) -> InlineKeyboardMarkup:
    """Создать клавиатуру для карточки истории"""
    buttons = []
    
    if has_active_run:
        buttons.append([InlineKeyboardButton(text=CONTINUE, callback_data=f"story_continue:{story_id}")])
    
    buttons.append([InlineKeyboardButton(text=START, callback_data=f"story_start:{story_id}")])
    buttons.append([InlineKeyboardButton(text=BACK, callback_data="show_stories:0")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# Функция get_service_buttons удалена - сервисные кнопки убраны из сцен
# Навигация только через ReplyKeyboard

def get_ending_keyboard(story_id: str, allow_restart: bool) -> InlineKeyboardMarkup:
    """Создать клавиатуру для финала"""
    buttons = []
    
    buttons.append([InlineKeyboardButton(text=OTHER_STORIES, callback_data="show_stories:0")])
    
    if allow_restart:
        buttons.append([InlineKeyboardButton(text=NEW_ATTEMPT, callback_data=f"story_restart:{story_id}")])
    
    buttons.append([InlineKeyboardButton(text=BACK_TO_MENU, callback_data="service_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@router.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    user = await UserRepository.get_or_create(
        message.from_user.id,
        message.from_user.username
    )
    
    # Проверяем активную историю
    all_runs = await RunRepository.get_all_active_runs()
    user_runs = [r for r in all_runs if r.user_id == user.user_id]
    
    if user_runs:
        welcome = WELCOME_WITH_ACTIVE
    else:
        welcome = WELCOME_TEXT
    
    await message.answer(
        welcome,
        reply_markup=get_main_keyboard()
    )

@router.message(F.text == "📚 Истории")
async def show_stories(message: Message):
    """Показать список историй"""
    stories = story_engine.list_stories()
    
    if not stories:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=BACK_TO_MENU, callback_data="service_menu")]
        ])
        await message.answer(
            NO_STORIES_TEXT,
            reply_markup=keyboard
        )
        return
    
    keyboard, _ = get_stories_inline_keyboard(page=0)
    await message.answer(STORIES_LIST_TEXT, reply_markup=keyboard)

@router.message(F.text == "🧭 Продолжить")
async def continue_story(message: Message):
    """Продолжить активную историю"""
    user_id = message.from_user.id
    
    all_runs = await RunRepository.get_all_active_runs()
    user_runs = [r for r in all_runs if r.user_id == user_id]
    
    if not user_runs:
        await message.answer(
            NO_ACTIVE_STORY,
            reply_markup=get_main_keyboard()
        )
        return
    
    # Берём последнюю активную попытку
    run = user_runs[-1]
    
    result = await story_engine.continue_story(run.run_id)
    if result:
        text, keyboard, run_id = result
        
        await message.answer(text, reply_markup=keyboard)
    else:
        await message.answer(
            ERROR_LOADING_STORY,
            reply_markup=get_main_keyboard()
        )

@router.message(F.text == "🔄 Новая попытка")
async def new_attempt(message: Message):
    """Новая попытка с подтверждением"""
    user_id = message.from_user.id
    
    all_runs = await RunRepository.get_all_active_runs()
    user_runs = [r for r in all_runs if r.user_id == user_id]
    
    if not user_runs:
        await message.answer(
            NOTHING_TO_RESET,
            reply_markup=get_main_keyboard()
        )
        return
    
    # Если одна активная история - сразу подтверждение
    if len(user_runs) == 1:
        run = user_runs[0]
        story = story_engine.get_story(run.story_id)
        title = story.get("title", run.story_id) if story else run.story_id
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да", callback_data=f"reset_confirm:{run.story_id}"),
                InlineKeyboardButton(text="❌ Нет", callback_data="reset_cancel")
            ]
        ])
        
        await message.answer(
            f"{CONFIRM_RESET}\n\nИстория: {title}",
            reply_markup=keyboard
        )
    else:
        # Несколько активных историй - выбор
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
        await message.answer("🔄 Выбери историю для сброса:", reply_markup=keyboard)

@router.message(F.text == "ℹ️ Помощь")
async def show_help(message: Message):
    """Показать справку"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📚 Истории", callback_data="show_stories:0")]
    ])
    
    await message.answer(HELP_TEXT, reply_markup=keyboard)

# Callback handlers
@router.callback_query(F.data.startswith("story_page:"))
async def change_story_page(callback: CallbackQuery):
    """Смена страницы списка историй"""
    page = int(callback.data.split(":")[1])
    keyboard, _ = get_stories_inline_keyboard(page=page)
    await callback.message.edit_text(STORIES_LIST_TEXT, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "story_page_info")
async def story_page_info(callback: CallbackQuery):
    """Информация о странице (неактивная кнопка)"""
    await callback.answer()

@router.callback_query(F.data.startswith("story_select:"))
async def process_story_selection(callback: CallbackQuery):
    """Обработка выбора истории - показать карточку"""
    story_id = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id
    
    story = story_engine.get_story(story_id)
    if not story:
        await callback.answer("❌ История не найдена", show_alert=True)
        await callback.message.edit_text(
            STORY_NOT_FOUND,
            reply_markup=get_stories_inline_keyboard()[0]
        )
        return
    
    # Проверяем активную попытку
    active_run = await RunRepository.get_active_run(user_id, story_id)
    has_active_run = active_run is not None
    
    # Проверяем allow_restart
    allow_restart = story.get("allow_restart", False)
    
    # Формируем карточку
    title = story.get("title", story_id)
    description = story.get("description", "")
    version = story.get("version", "1.0")
    
    card_text = get_story_card(title, description, version)
    
    keyboard = get_story_card_keyboard(story_id, user_id, has_active_run, allow_restart)
    
    await callback.message.edit_text(card_text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("story_start:"))
async def start_story(callback: CallbackQuery):
    """Запуск истории"""
    try:
        story_id = callback.data.split(":", 1)[1]
        user_id = callback.from_user.id
        
        await UserRepository.get_or_create(user_id, callback.from_user.username)
        
        story = story_engine.get_story(story_id)
        if not story:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=BACK_TO_STORIES, callback_data="show_stories:0")]
            ])
            await callback.message.edit_text(
                STORY_NOT_FOUND,
                reply_markup=keyboard
            )
            await callback.answer("❌ История не найдена", show_alert=True)
            return
        
        # Проверяем завершённые попытки
        from storage.db import db
        has_finished = False
        if db.connection:
            async with db.connection.execute(
                """SELECT 1 FROM runs 
                   WHERE user_id = ? AND story_id = ? AND is_finished = 1
                   LIMIT 1""",
                (user_id, story_id)
            ) as cursor:
                row = await cursor.fetchone()
                has_finished = row is not None
        
        allow_restart = story.get("allow_restart", False)
        
        if has_finished and not allow_restart:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=BACK_TO_STORIES, callback_data="show_stories:0")],
                [InlineKeyboardButton(text=BACK_TO_MENU, callback_data="service_menu")]
            ])
            await callback.message.edit_text(
                STORY_ALREADY_FINISHED,
                reply_markup=keyboard
            )
            await callback.answer()
            return
        
        # Сбрасываем предыдущую попытку, если есть
        await RunRepository.reset_run(user_id, story_id)
        
        # Запускаем новую попытку
        result = await story_engine.start_story(user_id, story_id)
        
        if result is None:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=BACK_TO_STORIES, callback_data="show_stories:0")]
            ])
            await callback.message.edit_text(
                ERROR_LOADING_STORY,
                reply_markup=keyboard
            )
            await callback.answer("❌ Ошибка запуска", show_alert=True)
            return
        
        text, keyboard, run_id = result
        
        # Сервисные кнопки убраны - навигация только через ReplyKeyboard
        if keyboard:
            run = await RunRepository._get_run_by_id(run_id)
            if run:
        
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка при запуске истории: {e}", exc_info=True)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=BACK_TO_STORIES, callback_data="show_stories:0")]
        ])
        await callback.message.edit_text(
            ERROR_LOADING_STORY,
            reply_markup=keyboard
        )
        await callback.answer("❌ Ошибка", show_alert=True)

@router.callback_query(F.data.startswith("story_continue:"))
async def continue_story_callback(callback: CallbackQuery):
    """Продолжить историю из карточки"""
    story_id = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id
    
    active_run = await RunRepository.get_active_run(user_id, story_id)
    if not active_run:
        await callback.answer("❌ Активная попытка не найдена", show_alert=True)
        return
    
    result = await story_engine.continue_story(active_run.run_id)
    if result:
        text, keyboard, run_id = result
        
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()
    else:
        await callback.answer("❌ Ошибка", show_alert=True)

@router.callback_query(F.data.startswith("show_stories:"))
async def show_stories_callback(callback: CallbackQuery):
    """Показать список историй через callback"""
    page = int(callback.data.split(":")[1]) if ":" in callback.data else 0
    keyboard, _ = get_stories_inline_keyboard(page=page)
    await callback.message.edit_text(STORIES_LIST_TEXT, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "service_menu")
async def service_menu(callback: CallbackQuery):
    """Вернуться в главное меню"""
    await callback.message.edit_text(
        "🏠 Главное меню\n\nИспользуй кнопки ниже:",
        reply_markup=None
    )
    await callback.answer()
    # Отправляем новое сообщение с клавиатурой
    await callback.message.answer(
        "Выбери действие:",
        reply_markup=get_main_keyboard()
    )

@router.callback_query(F.data.startswith("repeat_scene:"))
async def repeat_scene(callback: CallbackQuery):
    """Повторить текущую сцену"""
    parts = callback.data.split(":")
    run_id = int(parts[1])
    scene_id = parts[2]
    
    result = await story_engine.continue_story(run_id)
    if result:
        text, keyboard, run_id = result
        
        await callback.message.answer(text, reply_markup=keyboard)
        await callback.answer("✅ Сцена повторена")
    else:
        await callback.answer("❌ Ошибка", show_alert=True)

@router.callback_query(F.data.startswith("reset_select:"))
async def reset_select_story(callback: CallbackQuery):
    """Выбор истории для сброса"""
    story_id = callback.data.split(":", 1)[1]
    
    story = story_engine.get_story(story_id)
    title = story.get("title", story_id) if story else story_id
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да", callback_data=f"reset_confirm:{story_id}"),
            InlineKeyboardButton(text="❌ Нет", callback_data="reset_cancel")
        ]
    ])
    
    await callback.message.edit_text(
        f"{CONFIRM_RESET}\n\nИстория: {title}",
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
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📚 Истории", callback_data="show_stories:0")]
    ])
    
    await callback.message.edit_text(
        f"✅ Прогресс по истории «{title}» сброшен.\nМожешь начать заново.",
        reply_markup=keyboard
    )
    await callback.answer("✅ Прогресс сброшен")

@router.callback_query(F.data == "reset_cancel")
async def reset_cancel(callback: CallbackQuery):
    """Отмена сброса"""
    await callback.message.edit_text("❌ Сброс отменён.")
    await callback.answer()

@router.callback_query(F.data.startswith("story_restart:"))
async def restart_story(callback: CallbackQuery):
    """Перезапуск истории"""
    story_id = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id
    
    await RunRepository.reset_run(user_id, story_id)
    
    result = await story_engine.start_story(user_id, story_id)
    
    if result:
        text, keyboard, run_id = result
        
        # Сервисные кнопки убраны - навигация только через ReplyKeyboard
        if keyboard:
            run = await RunRepository._get_run_by_id(run_id)
            if run:
        
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer("✅ История перезапущена")
    else:
        await callback.answer("❌ Ошибка перезапуска", show_alert=True)
