"""
Движок истории - основная логика обработки сюжетов
"""
import yaml
from typing import Dict, Any, Optional
from pathlib import Path
from config import STORIES_DIR
from storage.repository import RunRepository, FlagRepository
from engine.conditions import ConditionChecker
from engine.effects import EffectApplier
from engine.scene_renderer import SceneRenderer
from utils.logger import logger

class StoryEngine:
    """Движок для обработки историй"""
    
    def __init__(self):
        self.stories: Dict[str, Dict[str, Any]] = {}
        self._load_stories()
    
    def _load_stories(self):
        """Загрузить все истории из директории stories"""
        stories_path = Path(STORIES_DIR)
        
        if not stories_path.exists():
            logger.warning(f"Директория историй не найдена: {STORIES_DIR}")
            return
        
        # Загружаем .yaml и .yml файлы
        yaml_files = list(stories_path.glob("*.yaml")) + list(stories_path.glob("*.yml"))
        
        for yaml_file in yaml_files:
            try:
                with open(yaml_file, "r", encoding="utf-8") as f:
                    story_data = yaml.safe_load(f)
                    
                    if not story_data:
                        logger.warning(f"Пустой файл истории: {yaml_file}")
                        continue
                    
                    story_id = story_data.get("id")
                    if not story_id:
                        logger.warning(f"История без ID: {yaml_file}")
                        continue
                    
                    self.stories[story_id] = story_data
                    logger.info(f"Загружена история: {story_id} ({yaml_file.name})")
            
            except yaml.YAMLError as e:
                logger.error(f"Ошибка парсинга YAML {yaml_file}: {e}")
            except Exception as e:
                logger.error(f"Ошибка загрузки истории {yaml_file}: {e}")
    
    def get_story(self, story_id: str) -> Optional[Dict[str, Any]]:
        """Получить историю по ID"""
        return self.stories.get(story_id)
    
    def list_stories(self) -> Dict[str, Dict[str, Any]]:
        """Получить список всех историй"""
        return self.stories.copy()
    
    def reload_stories(self):
        """Перезагрузить все истории из файлов"""
        self.stories.clear()
        self._load_stories()
        logger.info("Истории перезагружены")
    
    async def start_story(self, user_id: int, story_id: str) -> Optional[tuple[str, Any, int]]:
        """
        Начать историю
        
        Args:
            user_id: ID пользователя
            story_id: ID истории
        
        Returns:
            Кортеж (текст, клавиатура, run_id) или None если ошибка
        """
        story = self.get_story(story_id)
        if not story:
            logger.warning(f"История не найдена: {story_id}")
            return None
        
        # Проверяем, есть ли активная попытка
        active_run = await RunRepository.get_active_run(user_id, story_id)
        if active_run:
            logger.info(f"У пользователя {user_id} уже есть активная попытка истории {story_id}")
            return await self.continue_story(active_run.run_id)
        
        # Проверяем возможность перезапуска
        allow_restart = story.get("allow_restart", False)
        if not allow_restart:
            # Проверяем, была ли завершённая попытка
            # (это упрощённая проверка, можно расширить)
            logger.info(f"История {story_id} не позволяет перезапуск")
        
        # Начинаем новую попытку
        start_scene = story.get("start_scene")
        if not start_scene:
            logger.error(f"История {story_id} не имеет start_scene")
            return None
        
        run = await RunRepository.create(user_id, story_id, start_scene)
        
        return await self.continue_story(run.run_id)
    
    async def continue_story(self, run_id: int) -> Optional[tuple[str, Any, int]]:
        """
        Продолжить историю с текущей сцены
        
        Args:
            run_id: ID попытки прохождения
        
        Returns:
            Кортеж (текст, клавиатура, run_id) или None если ошибка
        """
        # Получаем данные попытки
        run = await RunRepository._get_run_by_id(run_id)
        if not run:
            logger.error(f"Попытка прохождения не найдена: {run_id}")
            return None
        
        story = self.get_story(run.story_id)
        if not story:
            logger.error(f"История не найдена: {run.story_id}")
            return None
        
        scene_id = run.current_scene
        
        # Проверяем, это финал?
        endings = story.get("endings", {})
        if scene_id in endings:
            return await self._render_ending(run_id, story, scene_id)
        
        # Проверяем, это сцена?
        scenes = story.get("scenes", {})
        if scene_id not in scenes:
            logger.error(f"Сцена не найдена: {scene_id} в истории {run.story_id}")
            return None
        
        scene = scenes[scene_id]
        renderer = SceneRenderer(run_id)
        flags = await FlagRepository.get_flags(run_id)
        
        text, keyboard = await renderer.render_scene(scene, scene_id, flags)
        
        return text, keyboard, run_id
    
    async def _render_ending(
        self, 
        run_id: int, 
        story: Dict[str, Any], 
        ending_id: str
    ) -> tuple[str, Any, int]:
        """
        Отрендерить финал
        
        Args:
            run_id: ID попытки прохождения
            story: Данные истории
            ending_id: ID финала
        
        Returns:
            Кортеж (текст, None (нет клавиатуры), run_id)
        """
        endings = story.get("endings", {})
        ending = endings.get(ending_id)
        
        if not ending:
            logger.error(f"Финал не найден: {ending_id}")
            return "Ошибка: финал не найден", None, run_id
        
        # Завершаем попытку
        await RunRepository.finish_run(run_id)
        
        renderer = SceneRenderer(run_id)
        flags = await FlagRepository.get_flags(run_id)
        
        text = renderer.render_ending(ending, ending_id, flags)
        
        return text, None, run_id
    
    async def process_choice(
        self, 
        run_id: int, 
        scene_id: str, 
        choice_id: str
    ) -> Optional[tuple[str, Any, int]]:
        """
        Обработать выбор игрока
        
        Args:
            run_id: ID попытки прохождения
            scene_id: ID текущей сцены
            choice_id: ID выбранного выбора
        
        Returns:
            Кортеж (текст, клавиатура, run_id) или None если ошибка
        """
        # Получаем данные попытки
        run = await RunRepository._get_run_by_id(run_id)
        if not run:
            logger.error(f"Попытка прохождения не найдена: {run_id}")
            return None
        
        story = self.get_story(run.story_id)
        if not story:
            logger.error(f"История не найдена: {run.story_id}")
            return None
        
        scenes = story.get("scenes", {})
        scene = scenes.get(scene_id)
        
        if not scene:
            logger.error(f"Сцена не найдена: {scene_id}")
            return None
        
        choices = scene.get("choices", [])
        choice = next((c for c in choices if c.get("id") == choice_id), None)
        
        if not choice:
            logger.error(f"Выбор не найден: {choice_id} в сцене {scene_id}")
            return None
        
        # Проверяем условия
        conditions = choice.get("conditions", [])
        checker = ConditionChecker(run_id)
        
        if not await checker.check_conditions(conditions):
            logger.debug(f"Условия не выполнены для выбора {choice_id}")
            return None
        
        # Применяем эффекты
        effects = choice.get("effects", [])
        applier = EffectApplier(run_id)
        await applier.apply_effects(effects)
        
        # Переходим на следующую сцену
        next_scene = choice.get("next_scene")
        if not next_scene:
            logger.error(f"Выбор {choice_id} не имеет next_scene")
            return None
        
        await RunRepository.update_scene(run_id, next_scene)
        
        # Продолжаем историю
        return await self.continue_story(run_id)
    
    def preview_scene(self, story_id: str, scene_id: str) -> Optional[str]:
        """
        Предпросмотр сцены (для админов)
        
        Args:
            story_id: ID истории
            scene_id: ID сцены
        
        Returns:
            Текст сцены или None
        """
        story = self.get_story(story_id)
        if not story:
            return None
        
        scenes = story.get("scenes", {})
        scene = scenes.get(scene_id)
        
        if not scene:
            return None
        
        return scene.get("text", "")

