# cadquery_parametric_addon/registration.py
import bpy
import importlib
import logging
import sys
from pathlib import Path

# --- Модули для регистрации ---
# Основные модули ядра (порядок важен для зависимостей)
core_modules_order = [
    ".core.exceptions", # Сначала исключения
    ".dependencies",    # Потом проверка зависимостей
    ".core.data_cache",
    ".core.sockets",
    ".core.cad_manager", # До сокетов и нод
    ".core.node_tree",
    ".core.update_system",
    ".core.event_system",
    ".core.handlers",
]

operators_modules_order = [
    
]
# Модули с UI и операторами
ui_modules_order = [
    ".operators.node_ops",
    ".operators.io_json",
    ".operators.process_mesh",
    ".ui.menus",
    ".ui.panels", 
]

# Модули с нодами (будут загружены динамически)
nodes_module_path = ".nodes"

# Вспомогательные модули
utils_modules = [
    ".utils.cq_utils",
    ".utils.blender_utils"
]


logger = logging.getLogger(__name__)

# Словарь для хранения зарегистрированных модулей
modules_registered = []


def find_node_modules(package_name):
    """Находит все модули с нодами в папке nodes."""
    node_modules = []
    nodes_dir = Path(__file__).parent / "nodes"
    # Ищем __init__.py в подпапках (категориях)
    for category_dir in nodes_dir.iterdir():
        if category_dir.is_dir():
            init_file = category_dir / "__init__.py"
            if init_file.exists():
                 # Добавляем сам __init__ категории
                 category_module_path = f"{package_name}.nodes.{category_dir.name}"
                 node_modules.append(category_module_path)
                 # Ищем .py файлы нод внутри категории
                 for node_file in category_dir.glob("*.py"):
                     if node_file.stem != "__init__":
                          node_module_path = f"{package_name}.nodes.{category_dir.name}.{node_file.stem}"
                          node_modules.append(node_module_path)

    # Также ищем __init__.py в корне nodes (для регистрации категорий)
    root_init = nodes_dir / "__init__.py"
    if root_init.exists():
         node_modules.insert(0, f"{package_name}.nodes") # Добавляем в начало

    return node_modules


def register_modules(module_list, package_name):
    """Регистрирует классы из списка модулей."""
    global modules_registered
    for module_path in module_list:
        try:
            # Используем относительный импорт от имени пакета аддона
            if module_path.startswith('.'):
                 # Преобразуем относительный путь в абсолютный для importlib
                 # Например, ".core.sockets" -> "cadquery_parametric_addon.core.sockets"
                 full_module_path = package_name + module_path
            else:
                 full_module_path = module_path

            # Импортируем модуль
            module = importlib.import_module(module_path, package=package_name)
            modules_registered.append(module)
            logger.debug(f"Imported module: {full_module_path}")

            # Если в модуле есть функция register(), вызываем ее
            if hasattr(module, "register") and callable(module.register):
                logger.debug(f"Calling register() in {full_module_path}")
                module.register()
            # Если есть список classes для регистрации
            elif hasattr(module, "classes") and isinstance(module.classes, (list, tuple)):
                 from bpy.utils import register_class
                 for cls in module.classes:
                     try:
                          register_class(cls)
                          logger.debug(f"Registered class {cls.__name__} from {full_module_path}")
                     except ValueError:
                          # Класс уже может быть зарегистрирован (например, базовый)
                          logger.warning(f"Class {cls.__name__} from {full_module_path} might already be registered.")
                     except Exception as e_cls:
                          logger.error(f"Failed to register class {cls.__name__} from {full_module_path}: {e_cls}")

        except ImportError as e_imp:
            logger.error(f"Failed to import module {module_path} (full: {full_module_path}): {e_imp}")
        except Exception as e_reg:
            logger.error(f"Error during registration of module {module_path} (full: {full_module_path}): {e_reg}", exc_info=True)


def unregister_modules():
    """Дерегистрирует классы из ранее зарегистрированных модулей в обратном порядке."""
    global modules_registered
    logger.debug(f"Unregistering {len(modules_registered)} modules...")
    for module in reversed(modules_registered):
        try:
            module_name = module.__name__ # Используем имя загруженного модуля
            if hasattr(module, "unregister") and callable(module.unregister):
                logger.debug(f"Calling unregister() in {module_name}")
                module.unregister()
            elif hasattr(module, "classes") and isinstance(module.classes, (list, tuple)):
                 from bpy.utils import unregister_class
                 for cls in reversed(module.classes):
                     try:
                          unregister_class(cls)
                          logger.debug(f"Unregistered class {cls.__name__} from {module_name}")
                     except RuntimeError:
                          # Класс мог быть уже дерегистрирован или не был зарегистрирован
                          logger.warning(f"Class {cls.__name__} from {module_name} might already be unregistered or was not registered.")
                     except Exception as e_cls:
                          logger.error(f"Failed to unregister class {cls.__name__} from {module_name}: {e_cls}")

        except Exception as e:
            logger.error(f"Error during unregistration of module {module_name}: {e}", exc_info=True)

    modules_registered.clear()
    logger.debug("Module unregistration complete.")


def register(package_name):
    """Главная функция регистрации аддона."""
    logger.info(f"Registering addon: {package_name}")
    global modules_registered
    modules_registered = [] # Очищаем на всякий случай

    # 1. Ядро
    register_modules(core_modules_order, package_name)

    # 2. Находим и регистрируем ноды
    node_modules = find_node_modules(package_name)
    register_modules(node_modules, package_name)

     # 2.1 Заполняем категории меню после регистрации нод
    try:
        # Импортируем словарь ИЗ ui.menus
        from .ui import menus as ui_menus_module
        # Логируем состояние ДО вызова
        logger.debug(f"Categories dictionary BEFORE fill: {ui_menus_module.node_categories}")

        from .nodes import fill_node_categories # Импортируем функцию заполнения
        fill_node_categories(ui_menus_module.node_categories) # Передаем словарь из ui.menus

        # Логируем состояние ПОСЛЕ вызова
        logger.debug(f"Categories dictionary AFTER fill: {ui_menus_module.node_categories}")
        logger.debug("Filled node categories for UI menu.")
    except Exception as e:
        logger.error(f"Failed to fill node categories: {e}", exc_info=True) # Добавляем exc_info

    # 3. UI и Операторы
    register_modules(ui_modules_order, package_name)

    # 4. Утилиты (обычно не требуют регистрации классов bpy)
    # Просто импортируем их, если нужно
    # for module_path in utils_modules:
    #     try:
    #         importlib.import_module(module_path, package=package_name)
    #     except ImportError as e:
    #         logger.error(f"Failed to import utility module {module_path}: {e}")

    logger.info("Addon registration finished.")


def unregister():
    """Главная функция дерегистрации аддона."""
    logger.info("Unregistering addon...")
    unregister_modules()
    logger.info("Addon unregistration finished.")