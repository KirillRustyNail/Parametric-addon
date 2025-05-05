# cadquery_parametric_addon/nodes/operations/union.py
import bpy
import logging

from ...core.node_tree import CadQueryNode
from ...core.sockets import CQObjectSocket
from ...core.cad_manager import cad_manager
from ...core.exceptions import NodeProcessingError, SocketConnectionError
from ...dependencies import cq # Нужен для проверки типов

logger = logging.getLogger(__name__)

class UnionNode(CadQueryNode):
    """Performs a boolean union of two CadQuery objects (A + B)."""
    bl_idname = 'CQPNode_OperationUnionNode'
    bl_label = 'Union (Boolean)'
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
        out_socket = self.outputs["Result"]

        # Сбрасываем выход на случай ошибки
        out_socket.sv_set(None)

        if not socket_a.is_linked or not socket_b.is_linked:
            raise SocketConnectionError(self, "Both input objects must be connected")

        # Получаем объекты
        try:
            obj_a = socket_a.sv_get()
            obj_b = socket_b.sv_get()
            logger.debug(f"UnionNode '{self.name}': Inputs received - obj_a type: {type(obj_a)}, obj_b type: {type(obj_b)}")
        except Exception as e:
            raise SocketConnectionError(self, f"Could not get input data: {e}")

        if obj_a is None or obj_b is None:
            raise NodeProcessingError(self, "One or both input objects are None")
        
        if not isinstance(obj_a, cq.Workplane):
             # Попытка обернуть Shape?
             if isinstance(obj_a, cq.Shape) and obj_a.isValid():
                  logger.warning(f"UnionNode '{self.name}': Object A is a Shape, attempting to wrap in Workplane.")
                  try:
                       obj_a = cq.Workplane("XY").add(obj_a)
                  except Exception as e_wrap:
                       raise NodeProcessingError(self, f"Failed to wrap Object A (Shape) in Workplane: {e_wrap}")
             else:
                  raise NodeProcessingError(self, f"Object A must be a valid Workplane or Shape, got {type(obj_a)}")

        # obj_b может быть Workplane или Shape
        if not isinstance(obj_b, (cq.Workplane, cq.Shape)):
             raise NodeProcessingError(self, f"Object B must be a Workplane or Shape, got {type(obj_b)}")
        # ------------------------------------------------------

        # Выполняем операцию 'union' через менеджер
        try:
            # Передаем подготовленные obj_a (Workplane) и obj_b (Workplane/Shape)
            result_obj = cad_manager.execute_operation(obj_a, obj_b, "union")
            # execute_operation должен вернуть Workplane
            if not isinstance(result_obj, cq.Workplane):
                 logger.error(f"UnionNode '{self.name}': cad_manager.execute_operation did not return a Workplane for 'union' (got {type(result_obj)}).")
                 # Попытка извлечь Shape и обернуть снова?
                 shape_val = None
                 if hasattr(result_obj, 'val') and callable(result_obj.val):
                     try:
                          val_res = result_obj.val();
                          if isinstance(val_res, cq.Shape) and val_res.isValid(): shape_val = val_res
                          elif isinstance(val_res, list) and val_res and isinstance(val_res[0], cq.Shape) and val_res[0].isValid(): shape_val = val_res[0]
                     except: pass
                 if shape_val:
                      logger.warning("Wrapping result in Workplane again.")
                      result_obj = cq.Workplane("XY").add(shape_val)
                 else:
                      raise NodeProcessingError(self, "Union operation returned invalid result type.")

            self.outputs["Result"].sv_set(result_obj) # Устанавливаем результат Workplane
            logger.debug(f"UnionNode '{self.name}': Union operation successful.")

        except Exception as e:
            # Ловим ошибки из cad_manager или при проверке типов
             logger.error(f"Error during union operation in node '{self.name}': {e}", exc_info=True)
             if isinstance(e, (NodeProcessingError, SocketConnectionError)): raise
             else: raise NodeProcessingError(self, f"Union operation failed: {e}")

# --- Список классов ---
classes = (
    UnionNode,
)
# Регистрация в registration.py