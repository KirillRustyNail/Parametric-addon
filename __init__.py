# cadquery_parametric_addon/__init__.py
import bpy
import logging
from . import registration # Импортируем наш модуль регистрации

bl_info = {
    "name": "CadQuery Parametric Nodes",
    "author": "Your Name",
    "version": (0, 1, 0),
    "blender": (4, 2, 0), # Минимальная версия Blender
    "location": "Node Editor > Add > CadQuery",
    "description": "Create parametric objects using CadQuery nodes",
    "warning": "Requires CadQuery library installed. Very experimental.",
    "doc_url": "", # Ссылка на документацию
    "category": "Node",
}

# --- Logging Setup ---
# Настраиваем базовый логгер при загрузке аддона
log_level = logging.DEBUG # Уровень логирования (INFO, WARNING, ERROR)
log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(level=log_level, format=log_format)
logger = logging.getLogger(__name__) # Логгер для этого файла

# --- Регистрация/Дерегистрация ---
def register():
    logger.info(f"Registering {bl_info['name']} version {bl_info['version']}")
    # Передаем имя пакета для корректного импорта
    registration.register(__name__)

def unregister():
    logger.info(f"Unregistering {bl_info['name']}")
    registration.unregister()

# Этот блок выполняется, если скрипт запускается напрямую (для тестов)
# if __name__ == "__main__":
#     # Здесь можно добавить код для ручной регистрации/дерегистрации
#     # в среде разработки без установки аддона.
#     # Например:
#     # unregister()
#     # register()
#     pass