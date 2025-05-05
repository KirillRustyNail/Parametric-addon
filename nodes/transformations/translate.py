# cadquery_parametric_addon/nodes/transformations/translate.py
import bpy
from bpy.props import FloatVectorProperty
import logging # Добавляем логгер

from ...core.node_tree import CadQueryNode
from ...core.sockets import CQObjectSocket, CQVectorSocket
# from ...core.cad_manager import cad_manager # Не нужен для translate
from ...core.exceptions import NodeProcessingError, SocketConnectionError
from ...dependencies import cq

logger = logging.getLogger(__name__) # Создаем логгер

class TranslateNode(CadQueryNode):
    """Translates (moves) a CadQuery object by a vector."""
    bl_idname = 'CQPNode_TransformationTranslateNode'
    bl_label = 'Translate'
    sv_category = 'Transformations'

    # --- Свойство Ноды ---
    translation_: FloatVectorProperty(
        name="Translation", default=(0.0, 0.0, 0.0), size=3, subtype='TRANSLATION',
        description="Vector to translate the object by",
        update=CadQueryNode.process_node
    )

    # --- Инициализация (убираем prop_name) ---
    def sv_init(self, context):
        """Initialize sockets."""
        self.inputs.new(CQObjectSocket.bl_idname, "Object In")
        self.inputs.new(CQVectorSocket.bl_idname, "Translation").prop_name = 'translation_' # <-- Вернули
        self.outputs.new(CQObjectSocket.bl_idname, "Object Out")

    # --- UI (рисуем только ошибки) ---
    def draw_buttons(self, context, layout):
        """Draw UI."""
        super().draw_buttons(context, layout) # Ошибки
        # Поле ввода будет нарисовано сокетом

    # --- Обработка (изменена логика получения данных) ---
    def process(self):
        """Node's core logic."""
        socket_obj = self.inputs["Object In"]
        socket_vec = self.inputs["Translation"]

        if not socket_obj.is_linked:
            raise SocketConnectionError(self, "'Object In' must be connected")

        try:
            obj_in = socket_obj.sv_get()
            # Получаем вектор: если сокет подключен - из него (sv_get вернет tuple),
            # иначе - из свойства НОДЫ (self.translation_ как tuple)
            translation_vec = socket_vec.sv_get(default=tuple(self.translation_))

            # logger.debug(f"Translate node: input obj type {type(obj_in)}, vector {translation_vec}")

            # Проверка типа вектора (должен быть tuple/list из 3 чисел)
            if not isinstance(translation_vec, (tuple, list)) or len(translation_vec) != 3:
                try:
                    translation_vec = tuple(translation_vec)
                    if len(translation_vec) != 3: raise ValueError
                except (TypeError, ValueError):
                    raise NodeProcessingError(self, f"Invalid translation vector type or size: {translation_vec} ({type(translation_vec)})")

            if obj_in is None:
                raise NodeProcessingError(self, "Input object is None")

        except NodeProcessingError: raise # Передаем наши ошибки
        except Exception as e:
             # Ловим NoDataError или другие ошибки
            raise NodeProcessingError(self, f"Input error: {e}")


        # Выполняем операцию translate напрямую
        try:
            if hasattr(obj_in, 'translate'):
                result_obj = obj_in.translate(translation_vec)
                self.outputs["Object Out"].sv_set(result_obj)
                # logger.debug(f"  Translate result type: {type(result_obj)}")
            else:
                raise NodeProcessingError(self, f"Input object of type {type(obj_in)} does not support 'translate'")

        except Exception as e:
            raise NodeProcessingError(self, f"Translate operation failed: {e}")


# --- Registration ---
classes = (
    TranslateNode,
)

# Код register/unregister убран отсюда