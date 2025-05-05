# cadquery_parametric_addon/dependencies.py
import logging
import sys
import os

logger = logging.getLogger(__name__)
cadquery_available = False
cq = None
custom_cq_path = r"C:\blender_python\Lib\site-packages" # Используем raw string
sys.path.append(custom_cq_path)

try:
    import cadquery as cq
    # Проверка версии (опционально, но рекомендуется)
    # from importlib.metadata import version
    # cq_version = version("cadquery")
    # if cq_version < "2.5.2":
    #     logger.warning(f"CadQuery version {cq_version} is older than recommended 2.5.2.")
    cadquery_available = True
    logger.info("CadQuery library found and imported successfully.")
except ImportError:
    logger.warning("CadQuery library not found. Please install it for this addon to function.")
    cadquery_available = False
except Exception as e:
    logger.error(f"An unexpected error occurred while importing CadQuery: {e}")
    cadquery_available = False

def check_dependencies():
    if not cadquery_available:
        # Можно показать сообщение пользователю здесь
        print("ERROR: CadQueryParametricAddon requires the 'cadquery' library to be installed.")
    return cadquery_available