"""
FSM состояния для админ-команд
"""
from aiogram.fsm.state import State, StatesGroup

class EditTextStates(StatesGroup):
    """Состояния для редактирования текста"""
    waiting_for_text = State()
    waiting_for_next_line = State()

class EditChoiceStates(StatesGroup):
    """Состояния для редактирования выбора"""
    waiting_for_choice_id = State()
    waiting_for_choice_text = State()
    waiting_for_next_scene = State()
    waiting_for_condition_type = State()
    waiting_for_condition_value = State()
    waiting_for_effect_type = State()
    waiting_for_effect_value = State()

class UploadStoryStates(StatesGroup):
    """Состояния для загрузки истории"""
    waiting_for_yaml_text = State()
    waiting_for_overwrite_confirm = State()

class DeleteStoryStates(StatesGroup):
    """Состояния для удаления истории"""
    waiting_for_delete_confirm = State()

class PreviewStoryStates(StatesGroup):
    """Состояния для preview истории"""
    preview_mode = State()
