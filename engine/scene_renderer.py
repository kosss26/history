"""
Рендеринг сцен для Telegram
"""
from typing import Dict, Any, List, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import DEBUG
from storage.repository import FlagRepository

class SceneRenderer:
    """Рендеринг сцен и выборов"""
    
    def __init__(self, run_id: int):
        self.run_id = run_id
    
    async def render_scene(
        self, 
        scene: Dict[str, Any], 
        scene_id: str,
        flags: Optional[Dict[str, str]] = None
    ) -> tuple[str, InlineKeyboardMarkup]:
        """
        Отрендерить сцену
        
        Args:
            scene: Данные сцены из YAML
            scene_id: ID сцены
            flags: Словарь флагов (опционально)
        
        Returns:
            Кортеж (текст сообщения, клавиатура)
        """
        text = scene.get("text", "")
        
        # Добавляем debug-информацию
        if DEBUG:
            debug_info = f"\n\n[DEBUG]\nСцена: {scene_id}\nRun ID: {self.run_id}"
            
            if flags is None:
                flags = await FlagRepository.get_flags(self.run_id)
            
            if flags:
                flags_str = ", ".join(f"{k}={v}" for k, v in flags.items())
                debug_info += f"\nФлаги: {flags_str}"
            
            text += debug_info
        
        # Формируем клавиатуру с выбором
        choices = scene.get("choices", [])
        keyboard = self._build_keyboard(choices, scene_id)
        
        return text, keyboard
    
    def _build_keyboard(
        self, 
        choices: List[Dict[str, Any]], 
        scene_id: str
    ) -> InlineKeyboardMarkup:
        """
        Построить клавиатуру с выбором
        
        Args:
            choices: Список выборов
            scene_id: ID текущей сцены
        
        Returns:
            InlineKeyboardMarkup
        """
        buttons = []
        
        for choice in choices:
            choice_id = choice.get("id", "")
            choice_text = choice.get("text", "")
            
            # Callback data: choice:<run_id>:<scene_id>:<choice_id>
            callback_data = f"choice:{self.run_id}:{scene_id}:{choice_id}"
            
            buttons.append([
                InlineKeyboardButton(text=choice_text, callback_data=callback_data)
            ])
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def render_ending(
        self, 
        ending: Dict[str, Any], 
        ending_id: str,
        flags: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Отрендерить финал
        
        Args:
            ending: Данные финала из YAML
            ending_id: ID финала
            flags: Словарь флагов (опционально)
        
        Returns:
            Текст сообщения
        """
        text = ending.get("text", "")
        ending_type = ending.get("ending_type", "neutral")
        
        # Добавляем debug-информацию
        if DEBUG:
            debug_info = f"\n\n[DEBUG]\nФинал: {ending_id}\nТип: {ending_type}\nRun ID: {self.run_id}"
            
            if flags:
                flags_str = ", ".join(f"{k}={v}" for k, v in flags.items())
                debug_info += f"\nФлаги: {flags_str}"
            
            text += debug_info
        
        return text
