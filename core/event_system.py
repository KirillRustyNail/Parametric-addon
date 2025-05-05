# cadquery_parametric_addon/core/event_system.py
import logging
from .update_system import update_manager # Импортируем UpdateManager

logger = logging.getLogger(__name__)

# --- Event Classes (Простые классы для передачи информации) ---
class BaseEvent:
    pass

class TreeEvent(BaseEvent):
    """Событие, связанное с деревом нод (изменение структуры)."""
    def __init__(self, tree):
        self.tree = tree

    def __repr__(self):
        return f"<TreeEvent tree='{self.tree.name}'>"

class PropertyEvent(BaseEvent):
    """Событие изменения свойства ноды."""
    def __init__(self, tree, updated_nodes):
        self.tree = tree
        self.updated_nodes = updated_nodes # Список измененных нод

    def __repr__(self):
        node_names = [n.name for n in self.updated_nodes]
        return f"<PropertyEvent tree='{self.tree.name}' nodes={node_names}>"

class SceneEvent(BaseEvent):
     """Событие изменения сцены (если нужно)."""
     # Пока не используется активно
     pass

class FileEvent(BaseEvent):
     """Событие загрузки файла."""
     pass


# --- Event Handling ---
def handle_event(event: BaseEvent):
    """Main entry point for processing events."""
    # logger.debug(f"Handling event: {event}")

    if isinstance(event, TreeEvent):
        # logger.debug(f"Tree structure changed: {event.tree.name}")
        # Помечаем все дерево как требующее пересчета топологии и обновления
        update_manager.mark_tree_dirty(event.tree)
        update_manager.request_update(event.tree)

    elif isinstance(event, PropertyEvent):
        logger.debug(f"Handling PropertyEvent for tree {event.tree.name}, nodes {[n.name for n in event.updated_nodes]}") # Лог 1
        # Помечаем конкретные ноды как устаревшие
        update_manager.mark_nodes_dirty(event.tree, event.updated_nodes)
        logger.debug(f"  Called update_manager.mark_nodes_dirty") # Лог 2
        update_manager.request_update(event.tree) # Запрашиваем обновление всего дерева
        logger.debug(f"  Called update_manager.request_update") # Лог 3

    elif isinstance(event, FileEvent):
        # logger.debug("File loaded event.")
        # Очищаем все кеши и состояния при загрузке нового файла
        update_manager.clear_all_states()
        # Импортируем здесь, чтобы избежать цикла
        from .data_cache import clear_all_socket_cache
        clear_all_socket_cache()

    # elif isinstance(event, SceneEvent):
    #     # Обработка изменений сцены (если включено в настройках дерева)
    #     # Нужно будет пройти по всем деревьям и обновить те, что подписаны
    #     pass

    else:
        logger.warning(f"Unhandled event type: {type(event)}")