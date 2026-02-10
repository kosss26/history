"""
Расширенные админ-команды для редактирования историй
"""
import re
from io import BytesIO
from typing import Optional, Dict, Any, List
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Document
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_USER_IDS
from engine import story_engine
from utils.yaml_utils import (
    parse_yaml, save_story, load_story_file, story_exists, delete_story,
    get_story_summary, validate_story, format_story_yaml, sanitize_story_id, MAX_TEXT_LENGTH
)
from utils.logger import logger

router = Router(name="admin_editor")

def is_admin(user_id: int) -> bool:
    """Проверить, является ли пользователь администратором"""
    return user_id in ADMIN_USER_IDS

# FSM States
class EditTextStates(StatesGroup):
    waiting_for_text = State()
    waiting_for_next_line = State()

class EditChoiceStates(StatesGroup):
    waiting_for_choice_id = State()
    waiting_for_choice_text = State()
    waiting_for_next_scene = State()
    waiting_for_condition_type = State()
    waiting_for_condition_value = State()
    waiting_for_effect_type = State()
    waiting_for_effect_value = State()

class UploadStoryStates(StatesGroup):
    waiting_for_yaml_text = State()
    waiting_for_overwrite_confirm = State()

class DeleteStoryStates(StatesGroup):
    waiting_for_delete_confirm = State()

# ==================== ГЛАВНОЕ МЕНЮ ====================

@router.message(Command("admin"))
async def cmd_admin_menu(message: Message):
    """Главное меню админа"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещён. Только для администраторов.")
        return
    
    text = (
        "🔧 Админ-панель\n\n"
        "Доступные команды:\n"
        "• /admin_stories - Список историй\n"
        "• /admin_edit <story_id> - Редактировать историю\n"
        "• /admin_upload - Загрузить историю (YAML)\n"
        "• /admin_export <story_id> - Экспортировать историю\n"
        "• /admin_delete <story_id> - Удалить историю\n"
        "• /admin_reload - Перезагрузить истории\n"
        "• /admin_validate <story_id> - Валидировать историю\n"
        "• /admin_preview <story_id> - Предпросмотр истории\n\n"
        "Старые команды:\n"
        "• /start_story, /reset_story, /preview_scene, /active_runs"
    )
    await message.answer(text)

# ==================== СПИСОК ИСТОРИЙ ====================

@router.message(Command("admin_stories"))
async def cmd_admin_stories(message: Message):
    """Список всех историй"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещён.")
        return
    
    stories = story_engine.list_stories()
    
    if not stories:
        await message.answer("📚 Истории не найдены.")
        return
    
    lines = ["📚 Список историй:\n"]
    
    for story_id, story_data in stories.items():
        title = story_data.get("title", "Без названия")
        version = story_data.get("version", "1.0")
        scenes_count = len(story_data.get("scenes", {}))
        endings_count = len(story_data.get("endings", {}))
        
        lines.append(
            f"• {title}\n"
            f"  ID: {story_id}\n"
            f"  Версия: {version}\n"
            f"  Сцен: {scenes_count}, Финалов: {endings_count}\n"
        )
    
    text = "\n".join(lines)
    
    if len(text) > 4096:
        chunks = [text[i:i+4096] for i in range(0, len(text), 4096)]
        for chunk in chunks:
            await message.answer(chunk)
    else:
        await message.answer(text)

# ==================== РЕДАКТИРОВАНИЕ ТЕКСТА ====================

@router.message(Command("admin_edit_text"))
async def cmd_edit_text(message: Message, state: FSMContext):
    """Начать редактирование текста сцены"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещён.")
        return
    
    args = message.text.split()[1:] if message.text else []
    
    if len(args) < 2:
        await message.answer(
            "❌ Использование: /admin_edit_text <story_id> <scene_id>\n\n"
            "Режимы ввода:\n"
            "• Отправьте текст одним сообщением\n"
            "• Или отправьте 'добавить строку' для многострочного ввода, затем текст, затем 'завершить'"
        )
        return
    
    story_id = args[0]
    scene_id = args[1]
    
    story = story_engine.get_story(story_id)
    if not story:
        await message.answer(f"❌ История '{story_id}' не найдена.")
        return
    
    scenes = story.get("scenes", {})
    if scene_id not in scenes:
        await message.answer(f"❌ Сцена '{scene_id}' не найдена в истории '{story_id}'.")
        return
    
    await state.update_data(story_id=story_id, scene_id=scene_id)
    await state.set_state(EditTextStates.waiting_for_text)
    
    current_text = scenes[scene_id].get("text", "")
    
    await message.answer(
        f"✏️ Редактирование текста сцены '{scene_id}'\n\n"
        f"Текущий текст:\n{current_text}\n\n"
        f"Отправьте новый текст одним сообщением или начните многострочный ввод командой 'добавить строку'"
    )

@router.message(StateFilter(EditTextStates.waiting_for_text), F.text == "добавить строку")
async def start_multiline_text(message: Message, state: FSMContext):
    """Начать многострочный ввод"""
    await state.set_state(EditTextStates.waiting_for_next_line)
    await state.update_data(text_lines=[])
    
    await message.answer(
        "📝 Многострочный режим активирован.\n"
        "Отправляйте строки текста по одной.\n"
        "Отправьте 'завершить' чтобы закончить."
    )

@router.message(StateFilter(EditTextStates.waiting_for_next_line))
async def process_text_line(message: Message, state: FSMContext):
    """Обработка строки многострочного ввода"""
    if message.text == "завершить":
        data = await state.get_data()
        text_lines = data.get("text_lines", [])
        full_text = "\n".join(text_lines)
        
        story_id = data["story_id"]
        scene_id = data["scene_id"]
        
        # Сохраняем изменения
        success, error = await save_scene_text(story_id, scene_id, full_text)
        
        if success:
            await message.answer(f"✅ Текст сцены '{scene_id}' обновлён!")
            story_engine.reload_stories()
        else:
            await message.answer(f"❌ Ошибка: {error}")
        
        await state.clear()
        return
    
    # Добавляем строку
    data = await state.get_data()
    text_lines = data.get("text_lines", [])
    text_lines.append(message.text)
    await state.update_data(text_lines=text_lines)
    
    await message.answer(f"✅ Строка добавлена ({len(text_lines)} строк)")

@router.message(StateFilter(EditTextStates.waiting_for_text))
async def process_single_text(message: Message, state: FSMContext):
    """Обработка текста одним сообщением"""
    if len(message.text) > MAX_TEXT_LENGTH:
        await message.answer(
            f"❌ Текст слишком длинный (максимум {MAX_TEXT_LENGTH} символов).\n"
            f"Используйте многострочный режим: отправьте 'добавить строку'"
        )
        return
    
    data = await state.get_data()
    story_id = data["story_id"]
    scene_id = data["scene_id"]
    
    # Сохраняем изменения
    success, error = await save_scene_text(story_id, scene_id, message.text)
    
    if success:
        await message.answer(f"✅ Текст сцены '{scene_id}' обновлён!")
        story_engine.reload_stories()
    else:
        await message.answer(f"❌ Ошибка: {error}")
    
    await state.clear()

async def save_scene_text(story_id: str, scene_id: str, text: str) -> tuple[bool, Optional[str]]:
    """Сохранить текст сцены"""
    try:
        # Загружаем историю из файла
        story_data, error = load_story_file(story_id)
        if error:
            return False, error
        
        # Обновляем текст
        if "scenes" not in story_data:
            story_data["scenes"] = {}
        
        if scene_id not in story_data["scenes"]:
            story_data["scenes"][scene_id] = {}
        
        story_data["scenes"][scene_id]["text"] = text
        
        # Сохраняем
        return save_story(story_id, story_data)
    except Exception as e:
        return False, str(e)

# ==================== УПРАВЛЕНИЕ ВЫБОРАМИ ====================

@router.message(Command("admin_choices"))
async def cmd_list_choices(message: Message):
    """Список выборов в сцене"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещён.")
        return
    
    args = message.text.split()[1:] if message.text else []
    
    if len(args) < 2:
        await message.answer("❌ Использование: /admin_choices <story_id> <scene_id>")
        return
    
    story_id = args[0]
    scene_id = args[1]
    
    story = story_engine.get_story(story_id)
    if not story:
        await message.answer(f"❌ История '{story_id}' не найдена.")
        return
    
    scenes = story.get("scenes", {})
    if scene_id not in scenes:
        await message.answer(f"❌ Сцена '{scene_id}' не найдена.")
        return
    
    choices = scenes[scene_id].get("choices", [])
    
    if not choices:
        await message.answer(f"📋 В сцене '{scene_id}' нет выборов.")
        return
    
    lines = [f"📋 Выборы в сцене '{scene_id}':\n"]
    
    for i, choice in enumerate(choices, 1):
        choice_id = choice.get("id", "unknown")
        choice_text = choice.get("text", "")
        next_scene = choice.get("next_scene", "")
        
        lines.append(
            f"{i}. ID: {choice_id}\n"
            f"   Текст: {choice_text}\n"
            f"   Следующая сцена: {next_scene}\n"
        )
    
    text = "\n".join(lines)
    await message.answer(text)

@router.message(Command("admin_add_choice"))
async def cmd_add_choice(message: Message, state: FSMContext):
    """Добавить выбор в сцену"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещён.")
        return
    
    args = message.text.split()[1:] if message.text else []
    
    if len(args) < 2:
        await message.answer("❌ Использование: /admin_add_choice <story_id> <scene_id>")
        return
    
    story_id = args[0]
    scene_id = args[1]
    
    story = story_engine.get_story(story_id)
    if not story:
        await message.answer(f"❌ История '{story_id}' не найдена.")
        return
    
    await state.update_data(story_id=story_id, scene_id=scene_id, choice_data={})
    await state.set_state(EditChoiceStates.waiting_for_choice_id)
    
    await message.answer("✏️ Добавление выбора\n\nОтправьте ID выбора:")

@router.message(StateFilter(EditChoiceStates.waiting_for_choice_id))
async def process_choice_id(message: Message, state: FSMContext):
    """Обработка ID выбора"""
    choice_id = message.text.strip()
    
    data = await state.get_data()
    story_id = data["story_id"]
    scene_id = data["scene_id"]
    choice_data = data.get("choice_data", {})
    
    # Проверяем, не существует ли уже такой ID
    story = story_engine.get_story(story_id)
    scenes = story.get("scenes", {})
    scene = scenes.get(scene_id, {})
    choices = scene.get("choices", [])
    
    if any(c.get("id") == choice_id for c in choices):
        await message.answer(f"❌ Выбор с ID '{choice_id}' уже существует. Используйте другой ID.")
        return
    
    choice_data["id"] = choice_id
    await state.update_data(choice_data=choice_data)
    await state.set_state(EditChoiceStates.waiting_for_choice_text)
    
    await message.answer("Отправьте текст выбора:")

@router.message(StateFilter(EditChoiceStates.waiting_for_choice_text))
async def process_choice_text(message: Message, state: FSMContext):
    """Обработка текста выбора"""
    choice_text = message.text
    
    data = await state.get_data()
    choice_data = data.get("choice_data", {})
    choice_data["text"] = choice_text
    await state.update_data(choice_data=choice_data)
    await state.set_state(EditChoiceStates.waiting_for_next_scene)
    
    # Показываем список сцен и финалов для выбора
    story_id = data["story_id"]
    story = story_engine.get_story(story_id)
    
    scenes = list(story.get("scenes", {}).keys())
    endings = list(story.get("endings", {}).keys())
    
    keyboard_buttons = []
    
    # Кнопки для сцен
    for scene_id_option in scenes[:10]:  # Ограничиваем до 10
        keyboard_buttons.append([
            InlineKeyboardButton(text=f"Сцена: {scene_id_option}", callback_data=f"next_scene:{scene_id_option}")
        ])
    
    # Кнопки для финалов
    for ending_id in endings[:10]:
        keyboard_buttons.append([
            InlineKeyboardButton(text=f"Финал: {ending_id}", callback_data=f"next_scene:{ending_id}")
        ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="✏️ Ввести вручную", callback_data="next_scene:manual")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    text = "Выберите следующую сцену/финал или введите вручную:"
    if len(scenes) > 10 or len(endings) > 10:
        text += "\n\n(Показаны первые 10, остальные можно ввести вручную)"
    
    await message.answer(text, reply_markup=keyboard)

@router.callback_query(F.data.startswith("next_scene:"))
async def process_next_scene_choice(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора следующей сцены"""
    next_scene = callback.data.split(":", 1)[1]
    
    if next_scene == "manual":
        await callback.message.edit_text("Введите ID следующей сцены/финала:")
        await state.set_state(EditChoiceStates.waiting_for_next_scene)
        await callback.answer()
        return
    
    data = await state.get_data()
    choice_data = data.get("choice_data", {})
    choice_data["next_scene"] = next_scene
    
    # Сохраняем выбор
    success, error = await save_choice(
        data["story_id"],
        data["scene_id"],
        choice_data
    )
    
    if success:
        await callback.message.edit_text(f"✅ Выбор добавлен!")
        story_engine.reload_stories()
    else:
        await callback.message.edit_text(f"❌ Ошибка: {error}")
    
    await callback.answer()
    await state.clear()

@router.message(StateFilter(EditChoiceStates.waiting_for_next_scene))
async def process_next_scene_manual(message: Message, state: FSMContext):
    """Обработка ручного ввода следующей сцены"""
    next_scene = message.text.strip()
    
    data = await state.get_data()
    choice_data = data.get("choice_data", {})
    choice_data["next_scene"] = next_scene
    
    # Сохраняем выбор
    success, error = await save_choice(
        data["story_id"],
        data["scene_id"],
        choice_data
    )
    
    if success:
        await message.answer(f"✅ Выбор добавлен!")
        story_engine.reload_stories()
    else:
        await message.answer(f"❌ Ошибка: {error}")
    
    await state.clear()

async def save_choice(story_id: str, scene_id: str, choice_data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """Сохранить выбор в сцену"""
    try:
        story_data, error = load_story_file(story_id)
        if error:
            return False, error
        
        if "scenes" not in story_data:
            story_data["scenes"] = {}
        
        if scene_id not in story_data["scenes"]:
            story_data["scenes"][scene_id] = {}
        
        if "choices" not in story_data["scenes"][scene_id]:
            story_data["scenes"][scene_id]["choices"] = []
        
        # Добавляем выбор
        story_data["scenes"][scene_id]["choices"].append(choice_data)
        
        return save_story(story_id, story_data)
    except Exception as e:
        return False, str(e)

@router.message(Command("admin_delete_choice"))
async def cmd_delete_choice(message: Message):
    """Удалить выбор из сцены"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещён.")
        return
    
    args = message.text.split()[1:] if message.text else []
    
    if len(args) < 3:
        await message.answer("❌ Использование: /admin_delete_choice <story_id> <scene_id> <choice_id>")
        return
    
    story_id = args[0]
    scene_id = args[1]
    choice_id = args[2]
    
    try:
        story_data, error = load_story_file(story_id)
        if error:
            await message.answer(f"❌ {error}")
            return
        
        scenes = story_data.get("scenes", {})
        if scene_id not in scenes:
            await message.answer(f"❌ Сцена '{scene_id}' не найдена.")
            return
        
        choices = scenes[scene_id].get("choices", [])
        original_count = len(choices)
        
        # Удаляем выбор
        scenes[scene_id]["choices"] = [c for c in choices if c.get("id") != choice_id]
        
        if len(scenes[scene_id]["choices"]) == original_count:
            await message.answer(f"❌ Выбор '{choice_id}' не найден в сцене '{scene_id}'.")
            return
        
        success, error = save_story(story_id, story_data)
        if success:
            await message.answer(f"✅ Выбор '{choice_id}' удалён из сцены '{scene_id}'!")
            story_engine.reload_stories()
        else:
            await message.answer(f"❌ Ошибка сохранения: {error}")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

# ==================== ЗАГРУЗКА ИСТОРИИ ====================

@router.message(Command("admin_upload"))
async def cmd_upload_story(message: Message, state: FSMContext):
    """Начать загрузку истории"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещён.")
        return
    
    await state.set_state(UploadStoryStates.waiting_for_yaml_text)
    await message.answer(
        "📤 Загрузка истории\n\n"
        "Отправьте YAML одним из способов:\n"
        "• Вставьте YAML текстом в сообщение\n"
        "• Отправьте файл .yaml или .yml"
    )

@router.message(StateFilter(UploadStoryStates.waiting_for_yaml_text), F.document)
async def process_upload_file(message: Message, state: FSMContext):
    """Обработка загрузки файла"""
    if not message.document:
        return
    
    file_name = message.document.file_name or ""
    if not (file_name.endswith(".yaml") or file_name.endswith(".yml")):
        await message.answer("❌ Файл должен иметь расширение .yaml или .yml")
        return
    
    try:
        # Скачиваем файл
        file = await message.bot.get_file(message.document.file_id)
        file_content = await message.bot.download_file(file.file_path)
        yaml_text = file_content.read().decode("utf-8")
        
        await process_yaml_upload(message, state, yaml_text)
    except Exception as e:
        await message.answer(f"❌ Ошибка чтения файла: {str(e)}")
        await state.clear()

@router.message(StateFilter(UploadStoryStates.waiting_for_yaml_text))
async def process_upload_text(message: Message, state: FSMContext):
    """Обработка загрузки текстом"""
    await process_yaml_upload(message, state, message.text)

async def process_yaml_upload(message: Message, state: FSMContext, yaml_text: str):
    """Обработка загруженного YAML"""
    # Парсим YAML
    story_data, error = parse_yaml(yaml_text)
    if error:
        await message.answer(f"❌ Ошибка парсинга YAML:\n{error}")
        await state.clear()
        return
    
    # Получаем story_id
    story_id = story_data.get("id")
    if not story_id:
        await message.answer("❌ YAML не содержит поле 'id'")
        await state.clear()
        return
    
    # Проверяем, существует ли уже
    if story_exists(story_id):
        await state.update_data(story_data=story_data, story_id=story_id)
        await state.set_state(UploadStoryStates.waiting_for_overwrite_confirm)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, перезаписать", callback_data=f"upload_confirm:{story_id}")],
            [InlineKeyboardButton(text="❌ Нет, отменить", callback_data="upload_cancel")]
        ])
        
        await message.answer(
            f"⚠️ История '{story_id}' уже существует.\n"
            f"Перезаписать?",
            reply_markup=keyboard
        )
        return
    
    # Сохраняем сразу
    success, error = save_story(story_id, story_data)
    if success:
        summary = get_story_summary(story_data)
        await message.answer(summary)
        story_engine.reload_stories()
    else:
        await message.answer(f"❌ Ошибка сохранения: {error}")
    
    await state.clear()

@router.callback_query(F.data.startswith("upload_confirm:"))
async def confirm_upload(callback: CallbackQuery, state: FSMContext):
    """Подтверждение перезаписи"""
    data = await state.get_data()
    story_data = data.get("story_data")
    story_id = data.get("story_id")
    
    if not story_data or not story_id:
        await callback.answer("❌ Ошибка: данные не найдены")
        return
    
    success, error = save_story(story_id, story_data)
    if success:
        summary = get_story_summary(story_data)
        await callback.message.edit_text(summary)
        story_engine.reload_stories()
        await callback.answer("✅ История сохранена")
    else:
        await callback.message.edit_text(f"❌ Ошибка сохранения: {error}")
        await callback.answer("❌ Ошибка")
    
    await state.clear()

@router.callback_query(F.data == "upload_cancel")
async def cancel_upload(callback: CallbackQuery, state: FSMContext):
    """Отмена загрузки"""
    await callback.message.edit_text("❌ Загрузка отменена")
    await callback.answer()
    await state.clear()

# ==================== ЭКСПОРТ ИСТОРИИ ====================

@router.message(Command("admin_export"))
async def cmd_export_story(message: Message):
    """Экспорт истории"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещён.")
        return
    
    args = message.text.split()[1:] if message.text else []
    
    if len(args) < 1:
        await message.answer("❌ Использование: /admin_export <story_id>")
        return
    
    story_id = args[0]
    
    story_data, error = load_story_file(story_id)
    if error:
        await message.answer(f"❌ {error}")
        return
    
    yaml_text = format_story_yaml(story_data)
    
    # Если текст помещается в сообщение, отправляем как текст
    if len(yaml_text) <= 4096:
        await message.answer(f"📄 История '{story_id}':\n\n```yaml\n{yaml_text}\n```", parse_mode=None)
    else:
        # Отправляем как документ
        file_data = BytesIO(yaml_text.encode("utf-8"))
        file_data.name = f"{story_id}.yaml"
        
        await message.answer_document(
            document=file_data,
            caption=f"📄 История '{story_id}'"
        )

# ==================== УДАЛЕНИЕ ИСТОРИИ ====================

@router.message(Command("admin_delete"))
async def cmd_delete_story(message: Message, state: FSMContext):
    """Удаление истории"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещён.")
        return
    
    args = message.text.split()[1:] if message.text else []
    
    if len(args) < 1:
        await message.answer("❌ Использование: /admin_delete <story_id>")
        return
    
    story_id = args[0]
    
    if not story_exists(story_id):
        await message.answer(f"❌ История '{story_id}' не найдена.")
        return
    
    await state.update_data(story_id=story_id)
    await state.set_state(DeleteStoryStates.waiting_for_delete_confirm)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"delete_confirm:{story_id}")],
        [InlineKeyboardButton(text="❌ Нет, отменить", callback_data="delete_cancel")]
    ])
    
    await message.answer(
        f"⚠️ Вы уверены, что хотите удалить историю '{story_id}'?",
        reply_markup=keyboard
    )

@router.callback_query(F.data.startswith("delete_confirm:"))
async def confirm_delete(callback: CallbackQuery, state: FSMContext):
    """Подтверждение удаления"""
    story_id = callback.data.split(":")[1]
    
    success, error = delete_story(story_id, move_to_deleted=True)
    if success:
        await callback.message.edit_text(f"✅ История '{story_id}' удалена (перемещена в _deleted)")
        story_engine.reload_stories()
        await callback.answer("✅ Удалено")
    else:
        await callback.message.edit_text(f"❌ Ошибка: {error}")
        await callback.answer("❌ Ошибка")
    
    await state.clear()

@router.callback_query(F.data == "delete_cancel")
async def cancel_delete(callback: CallbackQuery, state: FSMContext):
    """Отмена удаления"""
    await callback.message.edit_text("❌ Удаление отменено")
    await callback.answer()
    await state.clear()

# ==================== ПЕРЕЗАГРУЗКА ====================

@router.message(Command("admin_reload"))
async def cmd_reload_stories(message: Message):
    """Перезагрузка историй"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещён.")
        return
    
    story_engine.reload_stories()
    stories_count = len(story_engine.list_stories())
    await message.answer(f"✅ Истории перезагружены. Загружено: {stories_count}")

# ==================== ВАЛИДАЦИЯ ====================

@router.message(Command("admin_validate"))
async def cmd_validate_story(message: Message):
    """Валидация истории"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещён.")
        return
    
    args = message.text.split()[1:] if message.text else []
    
    if len(args) < 1:
        await message.answer("❌ Использование: /admin_validate <story_id>")
        return
    
    story_id = args[0]
    
    story_data, error = load_story_file(story_id)
    if error:
        await message.answer(f"❌ {error}")
        return
    
    is_valid, issues = validate_story(story_data)
    
    if is_valid and not issues:
        await message.answer(f"✅ История '{story_id}' валидна, ошибок не найдено!")
    elif is_valid:
        text = f"⚠️ История '{story_id}' валидна, но есть предупреждения:\n\n"
        text += "\n".join(f"• {issue}" for issue in issues)
        await message.answer(text)
    else:
        errors = [i for i in issues if "Отсутствует" in i or "не найден" in i or "не имеет" in i]
        warnings = [i for i in issues if i not in errors]
        
        text = f"❌ История '{story_id}' содержит ошибки:\n\n"
        if errors:
            text += "Ошибки:\n" + "\n".join(f"• {e}" for e in errors) + "\n\n"
        if warnings:
            text += "Предупреждения:\n" + "\n".join(f"• {w}" for w in warnings)
        
        if len(text) > 4096:
            chunks = [text[i:i+4096] for i in range(0, len(text), 4096)]
            for chunk in chunks:
                await message.answer(chunk)
        else:
            await message.answer(text)

# ==================== PREVIEW ====================

@router.message(Command("admin_preview"))
async def cmd_preview_story(message: Message):
    """Preview истории (тестовый режим)"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещён.")
        return
    
    args = message.text.split()[1:] if message.text else []
    
    if len(args) < 1:
        await message.answer("❌ Использование: /admin_preview <story_id>")
        return
    
    story_id = args[0]
    user_id = message.from_user.id
    
    # Запускаем в preview режиме (используем специальный префикс для run_id)
    # Для preview создаём отдельную запись с пометкой
    result = await story_engine.start_story(user_id, story_id)
    
    if result is None:
        await message.answer(f"❌ Ошибка: история '{story_id}' не найдена или не может быть запущена.")
        return
    
    text, keyboard, run_id = result
    
    # Добавляем пометку о preview режиме
    preview_text = f"🔍 [PREVIEW MODE] Run ID: {run_id}\n\n{text}"
    
    await message.answer(preview_text, reply_markup=keyboard)
