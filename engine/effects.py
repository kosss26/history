"""
Обработка эффектов выборов
"""
from typing import Dict, Any, List
from storage.repository import FlagRepository
from utils.logger import logger

class EffectApplier:
    """Применение эффектов"""
    
    def __init__(self, run_id: int):
        self.run_id = run_id
    
    async def apply_effects(self, effects: List[Dict[str, Any]]):
        """
        Применить список эффектов
        
        Args:
            effects: Список эффектов для применения
        """
        if not effects:
            return
        
        for effect in effects:
            await self._apply_single_effect(effect)
    
    async def _apply_single_effect(self, effect: Dict[str, Any]):
        """
        Применить один эффект
        
        Args:
            effect: Эффект для применения
        """
        effect_type = list(effect.keys())[0]
        effect_value = effect[effect_type]
        
        if effect_type == "add_flag":
            await self._add_flag(effect_value)
        elif effect_type == "remove_flag":
            await self._remove_flag(effect_value)
        elif effect_type == "set_flag":
            await self._set_flag(effect_value)
        elif effect_type == "increment_counter":
            await self._increment_counter(effect_value)
        else:
            logger.warning(f"Неизвестный тип эффекта: {effect_type}")
    
    async def _add_flag(self, flag_name: str):
        """Добавить флаг со значением '1'"""
        await FlagRepository.set_flag(self.run_id, flag_name, "1")
        logger.debug(f"Добавлен флаг: {flag_name}")
    
    async def _remove_flag(self, flag_name: str):
        """Удалить флаг"""
        await FlagRepository.remove_flag(self.run_id, flag_name)
        logger.debug(f"Удалён флаг: {flag_name}")
    
    async def _set_flag(self, flag_value: Dict[str, str]):
        """
        Установить флаг с конкретным значением
        
        Args:
            flag_value: Словарь с ключами 'flag' и 'value'
        """
        flag_name = flag_value.get("flag")
        value = flag_value.get("value", "1")
        
        if flag_name:
            await FlagRepository.set_flag(self.run_id, flag_name, str(value))
            logger.debug(f"Установлен флаг: {flag_name} = {value}")
    
    async def _increment_counter(self, counter_name: str):
        """
        Увеличить счётчик на 1
        
        Args:
            counter_name: Имя счётчика (хранится как флаг)
        """
        flags = await FlagRepository.get_flags(self.run_id)
        current_value = int(flags.get(counter_name, "0"))
        new_value = current_value + 1
        await FlagRepository.set_flag(self.run_id, counter_name, str(new_value))
        logger.debug(f"Увеличен счётчик: {counter_name} = {new_value}")
