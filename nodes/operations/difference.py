# cadquery_parametric_addon/nodes/operations/difference.py
import bpy
from ...core.node_tree import CadQueryNode
from ...core.sockets import CQObjectSocket
from ...core.cad_manager import cad_manager
from ...core.exceptions import NodeProcessingError, SocketConnectionError
from ...dependencies import cq # Нужен cq для проверки типов

class DifferenceNode(CadQueryNode):
    """Performs a boolean difference (cut) of two CadQuery objects (A - B)."""
    bl_idname = 'CQPNode_OperationDifferenceNode'
    bl_label = 'Difference (Cut)'
    sv_category = 'Operations'

    def sv_init(self, context):
        """Initialize sockets."""
        self.inputs.new(CQObjectSocket.bl_idname, "Object A (Base)")
        self.inputs.new(CQObjectSocket.bl_idname, "Object B (Tool)")
        self.outputs.new(CQObjectSocket.bl_idname, "Result")

    def draw_buttons(self, context, layout):
         super().draw_buttons(context, layout) # Ошибки
         # Можно добавить подсказку о порядке операндов
         layout.label(text="Output = A - B")

    def process(self):
        """Node's core logic."""
        socket_a = self.inputs["Object A (Base)"]
        socket_b = self.inputs["Object B (Tool)"]

        # Проверяем, подключены ли входы
        if not socket_a.is_linked or not socket_b.is_linked:
            raise SocketConnectionError(self, "Both input objects must be connected")

        # Получаем объекты
        try:
            obj_a = socket_a.sv_get() # Базовый объект
            obj_b = socket_b.sv_get() # Инструмент (вычитаемый)
        except Exception as e:
            raise SocketConnectionError(self, f"Could not get input data: {e}")

        if obj_a is None or obj_b is None:
            raise NodeProcessingError(self, "One or both input objects are None")

        # Проверяем типы (хотя cad_manager тоже может это делать)
        if not isinstance(obj_a, (cq.Workplane, cq.Shape)):
             raise NodeProcessingError(self, f"Object A must be Workplane/Shape, got {type(obj_a)}")
        # if not isinstance(obj_b, (cq.Workplane, cq.Shape)): # cad_manager обработает
        #      raise NodeProcessingError(self, f"Object B must be Workplane/Shape, got {type(obj_b)}")

        # Выполняем операцию 'cut' через менеджер
        try:
            # cut ожидает Shape или Workplane для второго аргумента
            result_obj = cad_manager.execute_operation(obj_a, obj_b, "cut")
            self.outputs["Result"].sv_set(result_obj)
        except Exception as e:
            # Ловим ошибки CadQuery или менеджера
            raise NodeProcessingError(self, f"Difference (cut) operation failed: {e}")

# --- Список классов для регистрации ---
classes = (
    DifferenceNode,
)