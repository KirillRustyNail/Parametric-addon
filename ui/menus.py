# cadquery_parametric_addon/ui/menus.py
import bpy
import logging # Добавляем импорт logging
from ..core.node_tree import CadQueryNodeTree # Нужен ID нашего дерева


logger = logging.getLogger(__name__) # <--- Добавить эту строку для создания логгера

# --- Node Categories ---
# Сопоставление категорий с классами нод (заполняется при регистрации нод)
node_categories = {
    "Primitives": [],
    "Operations": [],
    "Transformations": [],
    "Input/Output": [],
    "Selectors": [],
    # Добавьте другие категории по мере необходимости
}
logger.debug(f"Initial node_categories defined in ui.menus: {node_categories.keys()}")

# --- Add Node Menu ---
class CQP_MT_NodeAddMenu(bpy.types.Menu):
    """Menu for adding CadQuery nodes."""
    bl_idname = "CQP_MT_NodeAddMenu"
    bl_label = "Add CadQuery Node"

    @classmethod
    def poll(cls, context):
        # Показываем меню только в нашем редакторе нод
        return context.space_data.tree_type == CadQueryNodeTree.bl_idname

    def draw(self, context):
        layout = self.layout
        # Получаем список зарегистрированных нод нашего типа
        # Это упрощенный вариант, лучше использовать node_categories
        # node_types = bpy.types.Node.bl_rna.get_subclasses_recursive('CQPNode_')

        for category, nodes in node_categories.items():
             if nodes: # Показываем категорию, только если в ней есть ноды
                layout.menu(f"CQP_MT_NodeAddMenu_{category}", text=category)


# --- Submenus for Categories ---
# Динамически создаем подменю для каждой категории
def create_category_menus():
    created_menus = []
    logger.debug(f"Creating category menus. Source categories: {node_categories.keys()}")
    category_keys = list(node_categories.keys())

    for category_name in category_keys:
        menu_idname = f"CQP_MT_NodeAddMenu_{category_name}"
        menu_label = category_name
        logger.debug(f"  Preparing menu class for '{category_name}' (ID: {menu_idname})")

        def generate_draw_func(cat_name):
            def draw_menu_func(self, context):
                # Используем захваченное имя категории
                draw_category_items(self.layout, cat_name)
            return draw_menu_func

        try:
            menu_class = type(
                menu_idname,
                (bpy.types.Menu,),
                {
                    "bl_idname": menu_idname,
                    "bl_label": menu_label,
                    "draw": generate_draw_func(category_name)
                }
            )
            created_menus.append(menu_class)
            logger.debug(f"    Successfully prepared menu class: {menu_idname}")
        except Exception as e:
             logger.error(f"    Error creating dynamic menu class {menu_idname}: {e}")

    logger.debug(f"Finished creating menu classes. Count: {len(created_menus)}")
    return created_menus

def draw_category_items(layout, category_name):
     """Рисует пункты меню для нод в указанной категории."""
     logger.debug(f"Drawing items for category: '{category_name}'")
     nodes_in_category = node_categories.get(category_name) # Не [] по умолчанию, чтобы видеть ошибку
     if nodes_in_category is None:
          logger.error(f"  Category '{category_name}' not found in node_categories dictionary!")
          layout.label(text=f"Error: Category '{category_name}' not found", icon='ERROR')
          return
     if not nodes_in_category:
         logger.debug(f"  No nodes found in category '{category_name}'.")
         layout.label(text="(empty)") # Показываем (empty) вместо ничего
         return

     # Убедимся, что в списке кортежи (idname, label)
     valid_nodes = [(nid, nlbl) for nid, nlbl in nodes_in_category if isinstance(nid, str) and isinstance(nlbl, str)]
     logger.debug(f"  Valid nodes in '{category_name}': {valid_nodes}")

     if not valid_nodes:
         layout.label(text="(no valid nodes)")
         return

     for node_idname, node_label in valid_nodes:
         op = layout.operator("node.add_node", text=node_label)
         op.type = node_idname
         op.use_transform = True

# --- Registration ---
classes = [
    CQP_MT_NodeAddMenu,
    # Динамически созданные меню категорий будут добавлены в register()
]
category_menu_classes = [] # Храним созданные классы здесь

def register():
    from bpy.utils import register_class
    global category_menu_classes

    logger.debug("Registering UI menus...")
    
    category_menu_classes = create_category_menus() # Создаем подменю *до* регистрации
    
    all_classes_to_register = classes + category_menu_classes
    logger.debug(f"  Attempting to register {len(all_classes_to_register)} menu classes.")
    for cls in all_classes_to_register:
        try:
            register_class(cls)
            logger.debug(f"    Registered menu class: {cls.__name__}")
        except ValueError:
            logger.warning(f"    Menu class {cls.__name__} might already be registered.")
        except Exception as e:
            logger.error(f"    Failed to register menu class {cls.__name__}: {e}")

    # Регистрируем основное меню и динамически созданные
    all_classes_to_register = classes + category_menu_classes
    for cls in all_classes_to_register:
         try:
             register_class(cls)
         except ValueError: # Может быть уже зарегистрировано при перезагрузке скриптов
             print(f"Class {cls.__name__} might already be registered.")
         except Exception as e:
             print(f"Failed to register class {cls.__name__}: {e}")


    # Добавляем наше основное меню в стандартное меню добавления нод (Shift+A)
    # (Код добавления в NODE_MT_add остается прежним)
    try:
        node_menu = bpy.types.NODE_MT_add

        logger.debug("UI menus registration finished.")
        # Используем лямбду для menu_draw внутри append/remove
        draw_func = lambda self, context: menu_draw(self.layout)
        node_menu.append(draw_func)
        # Сохраняем саму лямбду для удаления
        bpy.types.NODE_MT_add.cq_menu_draw_func = draw_func
    except Exception as e:
         print(f"Could not append to NODE_MT_add menu: {e}")


def menu_draw(layout):
     # Проверяем, что мы в правильном редакторе
    if bpy.context.space_data.tree_type == CadQueryNodeTree.bl_idname:
        layout.menu("CQP_MT_NodeAddMenu", text="CadQuery", icon='PLUGIN') # Используйте свой значок


def unregister():
    from bpy.utils import unregister_class
    global category_menu_classes

    # Удаляем добавленный пункт меню
    if hasattr(bpy.types.NODE_MT_add, 'cq_menu_draw_func'):
        try:
            bpy.types.NODE_MT_add.remove(bpy.types.NODE_MT_add.cq_menu_draw_func)
            del bpy.types.NODE_MT_add.cq_menu_draw_func
        except Exception as e:
            print(f"Could not remove from NODE_MT_add menu: {e}")

    # Дерегистрируем основное меню и динамически созданные
    all_classes_to_unregister = classes + category_menu_classes
    for cls in reversed(all_classes_to_unregister):
        try:
            unregister_class(cls)
        except RuntimeError:
            # logger.error(f"Failed to unregister menu class: {cls.__name__}") # Используйте logger, если настроен
            print(f"Failed to unregister menu class (may already be unregistered): {cls.__name__}")
        except Exception as e:
             print(f"Error unregistering class {cls.__name__}: {e}")

    category_menu_classes = [] # Очищаем список