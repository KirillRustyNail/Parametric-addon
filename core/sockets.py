# cadquery_parametric_addon/core/sockets.py
import bpy
from bpy.props import (
    StringProperty, FloatProperty, FloatVectorProperty, BoolProperty,
    IntProperty
)
from bpy.types import NodeSocket
import time # Для генерации ID
import logging # Добавляем логгер

from .data_cache import sv_get_socket, sv_set_socket, sv_forget_socket
from ..dependencies import cq # Импортируем объект cq из dependencies
from mathutils import Vector, Color, Euler, Quaternion 

logger = logging.getLogger(__name__) # Создаем логгер

# # --- Вспомогательная функция-колбэк для обновления ---
# def socket_value_update(self, context):
#     """Callback for socket default properties. Updates linked node property and triggers node processing."""
#     if not self.node: return

#     # --- Синхронизация со свойством ноды ---
#     prop_name_val = getattr(self, 'prop_name', None) # Используем безопасный getattr
#     if prop_name_val and hasattr(self.node, prop_name_val):
#         try:
#             current_socket_val = self.default_property
#             value_to_set = current_socket_val
#             if isinstance(current_socket_val, (bpy.types.bpy_prop_array, Vector, Color, Euler, Quaternion)):
#                  value_to_set = tuple(current_socket_val)

#             logger.info("😎");
#             logger.info(f"socket_value_update: Setting node '{self.node.name}' property '{prop_name_val}' to {value_to_set}")
#             setattr(self.node, prop_name_val, value_to_set)
#             # --- Проверка сразу после setattr ---
#             actual_node_value = getattr(self.node, prop_name_val)
#             logger.info(f"socket_value_update: Verified node property '{prop_name_val}' is now: {actual_node_value}")
#             # ------------------------------------
#         except Exception as e:
#             logger.error(f"Failed to set node property '{prop_name_val}' from socket '{self.name}': {e}", exc_info=True) # Добавим exc_info

def socket_value_update(self, context):
    """Callback for socket default properties. Updates linked node property and triggers node processing."""
    if not self.node: return

    prop_name_val = getattr(self, 'prop_name', None)
    if prop_name_val and hasattr(self.node, prop_name_val):
        try:
            current_socket_val = self.default_property # Это значение из UI сокета (может быть float)
            value_to_set = current_socket_val

            # --- Определяем ОЖИДАЕМЫЙ тип свойства НОДЫ ---
            node_prop_rna = self.node.bl_rna.properties.get(prop_name_val)
            expected_node_prop_type = None
            if node_prop_rna:
                expected_node_prop_type = node_prop_rna.type # 'INT', 'FLOAT', 'BOOL', 'FLOAT_VECTOR', etc.

            # --- Преобразование ТИПА перед записью в свойство НОДЫ ---
            if expected_node_prop_type == 'INT':
                # Если нода ожидает int, преобразуем значение из сокета (которое может быть float)
                try:
                    # Округляем и преобразуем в int
                    value_to_set = int(round(current_socket_val))
                    # logger.debug(f"  Converted socket value {current_socket_val} to int: {value_to_set} for node prop '{prop_name_val}'")
                except (ValueError, TypeError):
                     logger.warning(f"  Could not convert socket value {current_socket_val} to int for node prop '{prop_name_val}'. Using original.")
                     # Оставляем value_to_set как есть, setattr вызовет ошибку, если тип несовместим
            elif expected_node_prop_type == 'FLOAT_VECTOR' and isinstance(current_socket_val, (tuple, list, Vector)):
                 # Преобразуем в tuple для FloatVectorProperty
                 value_to_set = tuple(current_socket_val)
            elif expected_node_prop_type == 'BOOLEAN':
                 # Преобразуем в bool на всякий случай
                 value_to_set = bool(current_socket_val)

            # logger.debug(f"socket_value_update: Setting node '{self.node.name}' property '{prop_name_val}' to {value_to_set} (type: {type(value_to_set)})")
            setattr(self.node, prop_name_val, value_to_set) # <-- ЗАПИСЬ В СВОЙСТВО НОДЫ (теперь с правильным типом)
            
        except Exception as e:
            logger.error(f"Failed to set node property '{prop_name_val}' from socket '{self.name}': {e}", exc_info=True)

    # --- Триггер обновления ноды ---
    if hasattr(self.node, 'process_node') and callable(self.node.process_node):
        self.node.process_node(context)
    # -------------------------------

# --- Base Socket Class ---
class CadQuerySocketBase(NodeSocket):
    """Base class for sockets in the CadQuery Parametric Addon."""
    bl_idname_prefix = "CQP_" # Префикс для избежания конфликтов

    # --- ID Management (similar to Sverchok) ---
    s_id: StringProperty(options={'SKIP_SAVE'})

    prop_name: StringProperty(
        name="Node Property Name",
        description="Name of the node's property linked to this socket's default value UI",
        default=""
    )

    @property
    def socket_id(self):
        """Unique identifier for the socket instance."""
        if not self.s_id:
            # Генерируем ID на основе ID ноды, идентификатора сокета и типа (in/out)
            node_id = getattr(self.node, 'node_id', str(hash(self.node))) # Нужен node_id в базовой ноде
            self.s_id = str(hash(node_id + self.identifier + ('o' if self.is_output else 'i')))
        return self.s_id

    # --- Data Handling (Версия, опирающаяся на default_property сокета) ---
    def sv_get(self, default=None):
        """Get data from the cache or the socket's default_property or the provided default."""
        if self.is_output:
            raise RuntimeError(f"Cannot get data from output socket: {self.name}")

        if self.is_linked:
            # --- Получение из кеша ---
            from .exceptions import NoDataError
            try:
                link = self.links[0]
                from_socket = link.from_socket
                return sv_get_socket(from_socket.socket_id, self.node, self)
            except KeyError: raise NoDataError(self.node, self)
            except IndexError: raise NoDataError(self.node, self)
        else:
            # --- Получение из default_property СОКЕТА ---
            if hasattr(self, 'default_property') and self.default_property is not None:
                # logger.debug(f"Socket '{self.name}' in node '{self.node.name}' using its own default_property.")
                prop = self.default_property
                # Преобразуем в стандартные типы Python, если это массив bpy
                if isinstance(prop, (bpy.types.bpy_prop_array, tuple, list)):
                    return tuple(prop)
                return prop
            # --- Получение из default АРГУМЕНТА ---
            elif default is not None:
                # logger.debug(f"Socket '{self.name}' in node '{self.node.name}' using provided default value: {default}")
                return default
            # --- Ничего нет ---
            else:
                # logger.debug(f"Socket '{self.name}' in node '{self.node.name}' has no connection, no default_property, and no default provided.")
                from .exceptions import NoDataError
                raise NoDataError(self.node, self)


    def sv_set(self, data):
        """Set data into the cache for this socket."""
        if not self.is_output:
            raise RuntimeError(f"Cannot set data to input socket: {self.name}")
        sv_set_socket(self.socket_id, data)

    def sv_forget(self):
        """Remove data from the cache for this socket."""
        sv_forget_socket(self.socket_id)

    # --- UI Drawing (Рисуем default_property сокета, если не подключен) ---
    def draw(self, context, layout, node, text):
        """Draw the socket UI."""
        if self.is_output or self.is_linked:
            layout.label(text=text)
        # --- Рисуем default_property СОКЕТА, если он есть ---
        elif hasattr(self, 'default_property'):
            # Используем имя свойства 'default_property' самого сокета
            # text=text использует имя сокета как метку поля ввода
            layout.prop(self, "default_property", text=text)
        # ----------------------------------------------------
        else:
            # Просто показать метку, если нет значения по умолчанию
            layout.label(text=text)

    # --- Цвет сокета ---
    def draw_color(self, context, node):
        """Return the color of the socket."""
        # Этот метод устарел в 4.0+, используем draw_color_simple
        return self.draw_color_simple() # Вызываем новый метод для обратной совместимости?

    @classmethod
    def draw_color_simple(cls):
        """Return the color of the socket type."""
        # Переопределить в дочерних классах
        return (0.6, 0.6, 0.6, 1.0) # Серый по умолчанию

# --- Specific Socket Types (Добавляем update=socket_value_update) ---

class CQObjectSocket(CadQuerySocketBase):
    """Socket for passing CadQuery Workplane or Shape objects."""
    bl_idname = "CQP_ObjectSocket"
    bl_label = "CQ Object"
    # Нет default_property для UI

    @classmethod
    def draw_color_simple(cls):
        return (0.1, 0.4, 0.8, 1.0) # Синий

class CQNumberSocket(CadQuerySocketBase):
    """Socket for passing numerical values (float or int)."""
    bl_idname = "CQP_NumberSocket"
    bl_label = "Number"

    default_property: FloatProperty(
        name="Value", description="Default value if socket is not connected",
        default=1.0, # Ставим 0.0 по умолчанию для сокета
        update=socket_value_update # <--- Добавляем колбэк
    )

    @classmethod
    def draw_color_simple(cls):
        return (0.6, 1.0, 0.6, 1.0) # Зеленый
    
# --- Целочисленный сокет (НОВЫЙ) ---
class CQIntSocket(CadQuerySocketBase):
    """Socket for passing integer values."""
    bl_idname = "CQP_IntSocket"
    bl_label = "Integer"

    default_property: IntProperty( 
        name="Value", description="Default value if socket is not connected",
        default=1, 
        update=socket_value_update
    )

    @classmethod
    def draw_color_simple(cls):
        return (0.4, 0.8, 0.9, 1.0) # Голубой (для отличия)
    
class CQVectorSocket(CadQuerySocketBase):
    """Socket for passing 3D vectors (tuples of 3 floats)."""
    bl_idname = "CQP_VectorSocket"
    bl_label = "Vector"

    default_property: FloatVectorProperty(
        name="Vector", description="Default vector if socket is not connected",
        default=(0.0, 0.0, 0.0), size=3, subtype='XYZ',
        update=socket_value_update # <--- Добавляем колбэк
    )

    @classmethod
    def draw_color_simple(cls):
        return (0.9, 0.6, 0.2, 1.0) # Оранжевый

class CQSelectorSocket(CadQuerySocketBase):
    """Socket for passing element selection data (type and index/indices)."""
    bl_idname = "CQP_SelectorSocket"
    bl_label = "CQ Selector"
    # Нет default_property для UI

    @classmethod
    def draw_color_simple(cls):
        return (1.0, 0.5, 0.8, 1.0) # Розовый
    
class CQBooleanSocket(CadQuerySocketBase):
    """Socket for passing boolean values."""
    bl_idname = "CQP_BooleanSocket"
    bl_label = "Boolean"

    default_property: BoolProperty(
        name="Boolean", description="Default value if socket is not connected",
        default=False,
        update=socket_value_update # <--- Добавляем колбэк
    )

    @classmethod
    def draw_color_simple(cls):
        return (1.0, 0.4, 0.4, 1.0) # Красный

# --- Registration ---
# Список классов остается тем же
classes = (
    CQObjectSocket,
    CQNumberSocket,
    CQIntSocket,
    CQVectorSocket,
    CQBooleanSocket,
    CQSelectorSocket,
)

# Функции register/unregister остаются без изменений
def register():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)

def unregister():
    from bpy.utils import unregister_class
    for cls in reversed(classes):
        try:
            unregister_class(cls)
        except RuntimeError:
            # Используем стандартный print, если logger недоступен при дерегистрации
            print(f"Warning: Failed to unregister socket class: {cls.__name__}")