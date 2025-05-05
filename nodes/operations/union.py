# cadquery_parametric_addon/nodes/operations/union.py
import bpy
from ...core.node_tree import CadQueryNode
from ...core.sockets import CQObjectSocket
from ...core.cad_manager import cad_manager
from ...core.exceptions import NodeProcessingError, SocketConnectionError

class UnionNode(CadQueryNode):
    """Performs a boolean union of two CadQuery objects."""
    bl_idname = 'CQPNode_OperationUnionNode'
    bl_label = 'Union (Boolean)'
    sv_category = 'Operations'

    def sv_init(self, context):
        """Initialize sockets."""
        self.inputs.new(CQObjectSocket.bl_idname, "Object A")
        self.inputs.new(CQObjectSocket.bl_idname, "Object B")
        self.outputs.new(CQObjectSocket.bl_idname, "Result")

    def process(self):
        """Node's core logic."""
        socket_a = self.inputs["Object A"]
        socket_b = self.inputs["Object B"]

        # Проверяем, подключены ли входы
        if not socket_a.is_linked or not socket_b.is_linked:
             raise SocketConnectionError(self, "Both input objects must be connected")

        # Получаем объекты из входных сокетов
        try:
            obj_a = socket_a.sv_get()
            obj_b = socket_b.sv_get()
        except Exception as e: # Ловим NoDataError или другие ошибки сокетов
             raise SocketConnectionError(self, f"Could not get input data: {e}")


        if obj_a is None or obj_b is None:
             raise NodeProcessingError(self, "One or both input objects are None")

        # Выполняем операцию CadQuery через менеджер
        try:
            result_obj = cad_manager.execute_operation(obj_a, obj_b, "union")
            self.outputs["Result"].sv_set(result_obj)
        except Exception as e:
            raise NodeProcessingError(self, f"Union operation failed: {e}")

# --- Registration ---
classes = (
    UnionNode,
)

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
             logger.error(f"Failed to unregister node class: {cls.__name__}")