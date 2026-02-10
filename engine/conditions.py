"""
Обработка условий для выборов
"""
from typing import Dict, Any, List
from storage.repository import FlagRepository
from utils.logger import logger

class ConditionChecker:
    """Проверка условий"""
    
    def __init__(self, run_id: int):
        self.run_id = run_id
        self._flags_cache: Dict[str, str] = {}
    
    async def load_flags(self):
        """Загрузить флаги в кэш"""
        self._flags_cache = await FlagRepository.get_flags(self.run_id)
    
    async def check_conditions(self, conditions: List[Dict[str, Any]]) -> bool:
        """
        Проверить список условий
        
        Args:
            conditions: Список условий для проверки
        
        Returns:
            True если все условия выполнены
        """
        if not conditions:
            return True
        
        await self.load_flags()
        
        for condition in conditions:
            if not await self._check_single_condition(condition):
                return False
        
        return True
    
    async def _check_single_condition(self, condition: Dict[str, Any]) -> bool:
        """
        Проверить одно условие
        
        Args:
            condition: Условие для проверки
        
        Returns:
            True если условие выполнено
        """
        condition_type = list(condition.keys())[0]
        condition_value = condition[condition_type]
        
        if condition_type == "has_flag":
            return await self._check_has_flag(condition_value)
        elif condition_type == "not_has_flag":
            return not await self._check_has_flag(condition_value)
        elif condition_type == "flag_equals":
            return await self._check_flag_equals(condition_value)
        else:
            logger.warning(f"Неизвестный тип условия: {condition_type}")
            return False
    
    async def _check_has_flag(self, flag_name: str) -> bool:
        """Проверить наличие флага"""
        return flag_name in self._flags_cache
    
    async def _check_flag_equals(self, condition_value: Dict[str, str]) -> bool:
        """
        Проверить равенство флага значению
        
        Args:
            condition_value: Словарь с ключами 'flag' и 'value'
        """
        flag_name = condition_value.get("flag")
        expected_value = condition_value.get("value")
        
        if not flag_name or expected_value is None:
            return False
        
        actual_value = self._flags_cache.get(flag_name)
        return actual_value == str(expected_value)
