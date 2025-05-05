# cadquery_parametric_addon/core/handlers.py
import bpy
from bpy.app.handlers import persistent
import logging

from .event_system import handle_event, FileEvent # , SceneEvent (пока не используем)
from .data_cache import clear_all_socket_cache
from .update_system import update_manager

logger = logging.getLogger(__name__)

# --- Handlers ---

# @persistent # Раскомментировать, если нужен SceneEvent
# def on_depsgraph_update_post(scene):
#     """Handles changes in the dependency graph (scene changes)."""
#     # Этот обработчик может срабатывать очень часто.
#     # Нужна логика, чтобы фильтровать ненужные обновления.
#     # Например, проверять, изменились ли объекты, от которых зависят ноды.
#     # Пока отключен для простоты.
#     # logger.debug("Depsgraph updated")
#     # handle_event(SceneEvent())
#     pass


@persistent
def on_load_post(dummy):
    """Called after a Blender file is loaded."""
    logger.info("Blender file loaded. Clearing caches and states.")
    # Мы не передаем scene, так как он может быть не инициализирован полностью
    handle_event(FileEvent())
    # Можно добавить принудительное обновление всех деревьев после загрузки, если нужно
    # for tree in bpy.data.node_groups:
    #     if tree.bl_idname == 'CadQueryNodeTreeType':
    #         update_manager.mark_tree_dirty(tree)
    #         update_manager.request_update(tree)

@persistent
def on_save_pre(dummy):
    """Called before a Blender file is saved."""
    # Можно добавить очистку временных данных перед сохранением
    pass

# --- Registration ---
_handlers = [
    # (bpy.app.handlers.depsgraph_update_post, on_depsgraph_update_post), # Пока отключен
    (bpy.app.handlers.load_post, on_load_post),
    (bpy.app.handlers.save_pre, on_save_pre),
]

def register():
    for handler_list, func in _handlers:
        if func not in handler_list:
            handler_list.append(func)
    logger.debug("App handlers registered.")

def unregister():
    for handler_list, func in _handlers:
        if func in handler_list:
            handler_list.remove(func)
    logger.debug("App handlers unregistered.")