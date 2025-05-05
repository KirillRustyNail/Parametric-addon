# cadquery_parametric_addon/nodes/operations/intersect.py
import bpy
import logging

from ...core.node_tree import CadQueryNode
from ...core.sockets import CQObjectSocket
from ...core.cad_manager import cad_manager
from ...core.exceptions import NodeProcessingError, SocketConnectionError
from ...dependencies import cq

logger = logging.getLogger(__name__)

class IntersectNode(CadQueryNode):
    """Performs a boolean intersection of two CadQuery objects."""
    bl_idname = 'CQPNode_OperationIntersectNode'
    bl_label = 'Intersect (Boolean)'
    sv_category = 'Operations'

    def sv_init(self, context):
        """Initialize sockets."""
        self.inputs.new(CQObjectSocket.bl_idname, "Object A")
        self.inputs.new(CQObjectSocket.bl_idname, "Object B")
        self.outputs.new(CQObjectSocket.bl_idname, "Result")

    def draw_buttons(self, context, layout):
         super().draw_buttons(context, layout) # Ошибки

    def process(self):
        """Node's core logic."""
        socket_a = self.inputs["Object A"]
        socket_b = self.inputs["Object B"]

        if not socket_a.is_linked or not socket_b.is_linked:
            raise SocketConnectionError(self, "Both input objects must be connected")

        try:
            obj_a = socket_a.sv_get()
            obj_b = socket_b.sv_get()
        except Exception as e:
            raise SocketConnectionError(self, f"Could not get input data: {e}")

        if obj_a is None or obj_b is None:
            raise NodeProcessingError(self, "One or both input objects are None")

        # Выполняем операцию 'intersect' через менеджер
        try:
            # logger.debug(f"Node {self.name}: Intersecting {type(obj_a)} with {type(obj_b)}")
            result_obj = cad_manager.execute_operation(obj_a, obj_b, "intersect")
            self.outputs["Result"].sv_set(result_obj)
        except Exception as e:
            raise NodeProcessingError(self, f"Intersect operation failed: {e}")

# --- Список классов ---
classes = (
    IntersectNode,
)
# Регистрация в registration.py