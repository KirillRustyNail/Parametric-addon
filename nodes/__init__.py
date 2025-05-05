# cadquery_parametric_addon/nodes/__init__.py
import importlib
import pkgutil
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Эта функция будет вызываться из registration.py для заполнения
# словаря node_categories в ui.menus
def fill_node_categories(categories_dict):
    """
    Dynamically imports node modules and populates the categories dictionary
    for the UI menu based on the node's 'sv_category'.
    """
    logger.debug(f"Starting fill_node_categories. Initial categories_dict: {categories_dict.keys()}")
    nodes_root_dir = Path(__file__).parent
    found_nodes_count = 0

    # Импортируем базовый класс здесь один раз
    try:
        from ..core.node_tree import CadQueryNode
    except ImportError as e:
        logger.error(f"Critical: Cannot import CadQueryNode base class in fill_node_categories: {e}")
        return # Нет смысла продолжать без базового класса

    for category_dir in nodes_root_dir.iterdir():
        if category_dir.is_dir() and (category_dir / "__init__.py").exists():
            category_name_from_dir = category_dir.name # Имя папки
            logger.debug(f"Processing directory: {category_name_from_dir}")

            # Импортируем модули нод из этой категории
            for node_file in category_dir.glob("*.py"):
                if node_file.stem != "__init__":
                    module_name = f".{category_name_from_dir}.{node_file.stem}"
                    logger.debug(f"  Attempting to import module: {module_name}")
                    try:
                        module = importlib.import_module(module_name, __package__)
                        logger.debug(f"    Successfully imported {module_name}")

                        # Ищем классы, наследующие CadQueryNode
                        for attr_name in dir(module):
                            obj = getattr(module, attr_name)
                            # Проверяем, что это класс, он наследует CadQueryNode, и это не сам CadQueryNode
                            if isinstance(obj, type) and issubclass(obj, CadQueryNode) and obj is not CadQueryNode:
                                node_category = getattr(obj, 'sv_category', None)
                                node_label = getattr(obj, 'bl_label', None)
                                node_idname = getattr(obj, 'bl_idname', None)

                                logger.debug(f"      Found node class: {obj.__name__} (Category: {node_category}, Label: {node_label}, ID: {node_idname})")

                                if node_category and node_label and node_idname:
                                    # Убедимся, что ключ категории существует в словаре
                                    if node_category not in categories_dict:
                                        logger.warning(f"        Category '{node_category}' for node '{node_label}' not pre-defined in ui.menus. Adding it.")
                                        categories_dict[node_category] = []

                                    # --- Добавляем проверку на дубликат ---
                                    is_duplicate = False
                                    for existing_idname, _ in categories_dict[node_category]:
                                        if existing_idname == node_idname:
                                            is_duplicate = True
                                            logger.warning(f"        Node {node_idname} ('{node_label}') already found in category '{node_category}'. Skipping duplicate.")
                                            break
                                    # ---------------------------------------

                                    if not is_duplicate: # Добавляем, только если не дубликат
                                        categories_dict[node_category].append((node_idname, node_label))
                                        found_nodes_count += 1
                                        logger.debug(f"        Added '{node_label}' to category '{node_category}'")
                                else:
                                    logger.warning(f"      Skipping class {obj.__name__} in {module_name}: missing sv_category, bl_label, or bl_idname.")

                    except ImportError as e:
                        logger.error(f"    Failed to import node module {module_name}: {e}")
                    except Exception as e_inner:
                        logger.error(f"    Error processing node module {module_name}: {e_inner}", exc_info=True)

    # Сортируем ноды в каждой категории по имени
    logger.debug("Sorting nodes within categories...")
    for category in categories_dict:
        # Убедимся, что элементы - это кортежи перед сортировкой
        valid_items = [item for item in categories_dict[category] if isinstance(item, tuple) and len(item) == 2]
        invalid_items = [item for item in categories_dict[category] if not (isinstance(item, tuple) and len(item) == 2)]
        if invalid_items:
             logger.warning(f"  Invalid items found in category '{category}': {invalid_items}")
        categories_dict[category] = sorted(valid_items, key=lambda item: item[1]) # Сортировка по label

    logger.debug(f"Finished fill_node_categories. Found {found_nodes_count} nodes. Final categories_dict keys: {categories_dict.keys()}")
    # Выведем содержимое словаря для проверки
    for cat, nodes in categories_dict.items():
        logger.debug(f"  Category '{cat}': {nodes}")