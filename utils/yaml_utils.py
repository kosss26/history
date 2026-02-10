"""
Утилиты для работы с YAML файлами историй
"""
import yaml
import re
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from config import STORIES_DIR
from utils.logger import logger

# Максимальный размер текста на сообщение
MAX_TEXT_LENGTH = 8000

def sanitize_story_id(story_id: str) -> Optional[str]:
    """
    Очистка и валидация story_id для защиты от path traversal
    
    Args:
        story_id: ID истории
    
    Returns:
        Очищенный story_id или None если невалидный
    """
    if not story_id:
        return None
    
    # Удаляем опасные символы
    sanitized = re.sub(r'[^a-zA-Z0-9_-]', '', story_id)
    
    # Проверяем, что не пустой и не содержит путь
    if not sanitized or '/' in story_id or '\\' in story_id or '..' in story_id:
        return None
    
    return sanitized

def validate_story(story_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Валидация структуры истории
    
    Args:
        story_data: Данные истории из YAML
    
    Returns:
        Кортеж (валидна ли история, список ошибок/предупреждений)
    """
    errors = []
    warnings = []
    
    # Проверка обязательных полей
    if not story_data.get("id"):
        errors.append("Отсутствует обязательное поле 'id'")
    
    if not story_data.get("title"):
        warnings.append("Отсутствует поле 'title'")
    
    if not story_data.get("start_scene"):
        errors.append("Отсутствует обязательное поле 'start_scene'")
    
    # Проверка сцен
    scenes = story_data.get("scenes", {})
    if not scenes:
        errors.append("История должна содержать хотя бы одну сцену")
    
    start_scene = story_data.get("start_scene")
    if start_scene and start_scene not in scenes:
        # Проверяем, может это ending
        endings = story_data.get("endings", {})
        if start_scene not in endings:
            errors.append(f"start_scene '{start_scene}' не найден в scenes или endings")
    
    # Проверка сцен на наличие текста и валидность выборов
    for scene_id, scene in scenes.items():
        if not scene.get("text"):
            warnings.append(f"Сцена '{scene_id}' не содержит текста")
        
        choices = scene.get("choices", [])
        for i, choice in enumerate(choices):
            if not choice.get("id"):
                errors.append(f"Выбор #{i+1} в сцене '{scene_id}' не имеет id")
            
            if not choice.get("text"):
                warnings.append(f"Выбор #{i+1} в сцене '{scene_id}' не имеет текста")
            
            next_scene = choice.get("next_scene")
            if not next_scene:
                errors.append(f"Выбор '{choice.get('id', 'unknown')}' в сцене '{scene_id}' не имеет next_scene")
            else:
                # Проверяем, что next_scene существует
                endings = story_data.get("endings", {})
                if next_scene not in scenes and next_scene not in endings:
                    errors.append(
                        f"Выбор '{choice.get('id', 'unknown')}' в сцене '{scene_id}' "
                        f"ведёт на несуществующую сцену/финал '{next_scene}'"
                    )
    
    # Проверка финалов
    endings = story_data.get("endings", {})
    for ending_id, ending in endings.items():
        if not ending.get("text"):
            warnings.append(f"Финал '{ending_id}' не содержит текста")
        
        ending_type = ending.get("ending_type", "neutral")
        if ending_type not in ["success", "failure", "neutral"]:
            warnings.append(f"Финал '{ending_id}' имеет нестандартный ending_type: {ending_type}")
    
    is_valid = len(errors) == 0
    all_issues = errors + warnings
    
    return is_valid, all_issues

def parse_yaml(yaml_text: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Парсинг YAML текста
    
    Args:
        yaml_text: Текст YAML
    
    Returns:
        Кортеж (данные истории или None, ошибка или None)
    """
    try:
        data = yaml.safe_load(yaml_text)
        if not data:
            return None, "YAML файл пуст"
        return data, None
    except yaml.YAMLError as e:
        error_msg = f"Ошибка парсинга YAML: {str(e)}"
        logger.error(error_msg)
        return None, error_msg
    except Exception as e:
        error_msg = f"Неожиданная ошибка: {str(e)}"
        logger.error(error_msg)
        return None, error_msg

def save_story(story_id: str, story_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Сохранение истории в файл
    
    Args:
        story_id: ID истории
        story_data: Данные истории
    
    Returns:
        Кортеж (успешно ли сохранено, ошибка или None)
    """
    # Валидация story_id
    sanitized_id = sanitize_story_id(story_id)
    if not sanitized_id:
        return False, "Невалидный story_id"
    
    # Валидация данных
    is_valid, issues = validate_story(story_data)
    if not is_valid:
        errors = [i for i in issues if "Отсутствует" in i or "не найден" in i or "не имеет" in i]
        if errors:
            return False, f"Ошибки валидации: {'; '.join(errors[:3])}"
    
    # Сохранение
    try:
        stories_path = Path(STORIES_DIR)
        stories_path.mkdir(exist_ok=True)
        
        file_path = stories_path / f"{sanitized_id}.yaml"
        
        with open(file_path, "w", encoding="utf-8") as f:
            yaml.dump(story_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        
        logger.info(f"История сохранена: {sanitized_id}")
        return True, None
    except Exception as e:
        error_msg = f"Ошибка сохранения: {str(e)}"
        logger.error(error_msg)
        return False, error_msg

def load_story_file(story_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Загрузка истории из файла
    
    Args:
        story_id: ID истории
    
    Returns:
        Кортеж (данные истории или None, ошибка или None)
    """
    sanitized_id = sanitize_story_id(story_id)
    if not sanitized_id:
        return None, "Невалидный story_id"
    
    try:
        stories_path = Path(STORIES_DIR)
        file_path = stories_path / f"{sanitized_id}.yaml"
        
        if not file_path.exists():
            return None, f"Файл истории '{sanitized_id}' не найден"
        
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        if not data:
            return None, "Файл истории пуст"
        
        return data, None
    except yaml.YAMLError as e:
        return None, f"Ошибка парсинга YAML: {str(e)}"
    except Exception as e:
        return None, f"Ошибка загрузки: {str(e)}"

def story_exists(story_id: str) -> bool:
    """Проверить, существует ли история"""
    sanitized_id = sanitize_story_id(story_id)
    if not sanitized_id:
        return False
    
    stories_path = Path(STORIES_DIR)
    file_path = stories_path / f"{sanitized_id}.yaml"
    return file_path.exists()

def delete_story(story_id: str, move_to_deleted: bool = True) -> Tuple[bool, Optional[str]]:
    """
    Удаление истории
    
    Args:
        story_id: ID истории
        move_to_deleted: Переместить в _deleted вместо удаления
    
    Returns:
        Кортеж (успешно ли удалено, ошибка или None)
    """
    sanitized_id = sanitize_story_id(story_id)
    if not sanitized_id:
        return False, "Невалидный story_id"
    
    try:
        stories_path = Path(STORIES_DIR)
        file_path = stories_path / f"{sanitized_id}.yaml"
        
        if not file_path.exists():
            return False, f"Файл истории '{sanitized_id}' не найден"
        
        if move_to_deleted:
            # Перемещаем в _deleted
            deleted_path = stories_path / "_deleted"
            deleted_path.mkdir(exist_ok=True)
            
            deleted_file = deleted_path / f"{sanitized_id}.yaml"
            file_path.rename(deleted_file)
            logger.info(f"История перемещена в _deleted: {sanitized_id}")
        else:
            # Удаляем полностью
            file_path.unlink()
            logger.info(f"История удалена: {sanitized_id}")
        
        return True, None
    except Exception as e:
        error_msg = f"Ошибка удаления: {str(e)}"
        logger.error(error_msg)
        return False, error_msg

def get_story_summary(story_data: Dict[str, Any]) -> str:
    """
    Получить краткую сводку по истории
    
    Args:
        story_data: Данные истории
    
    Returns:
        Текст сводки
    """
    story_id = story_data.get("id", "unknown")
    title = story_data.get("title", "Без названия")
    version = story_data.get("version", "1.0")
    scenes_count = len(story_data.get("scenes", {}))
    endings_count = len(story_data.get("endings", {}))
    
    return (
        f"📖 История сохранена!\n\n"
        f"ID: {story_id}\n"
        f"Название: {title}\n"
        f"Версия: {version}\n"
        f"Сцен: {scenes_count}\n"
        f"Финалов: {endings_count}"
    )

def format_story_yaml(story_data: Dict[str, Any]) -> str:
    """
    Форматирование истории в YAML строку
    
    Args:
        story_data: Данные истории
    
    Returns:
        YAML строка
    """
    return yaml.dump(story_data, allow_unicode=True, default_flow_style=False, sort_keys=False)
