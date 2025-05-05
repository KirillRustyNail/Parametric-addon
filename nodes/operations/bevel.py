# cadquery_parametric_addon/nodes/operations/bevel.py
import bpy
from bpy.props import FloatProperty, IntProperty
import logging

from ...core.node_tree import CadQueryNode
from ...core.sockets import CQObjectSocket, CQSelectorSocket, CQNumberSocket
from ...core.exceptions import NodeProcessingError, SocketConnectionError
from ...dependencies import cq

logger = logging.getLogger(__name__)

class BevelNode(CadQueryNode):
    """Applies fillet (rounding) or chamfer to selected edges of a CadQuery object."""
    bl_idname = 'CQPNode_OperationBevelNode'
    bl_label = 'Bevel (Fillet/Chamfer)'
    sv_category = 'Operations'

    # --- Свойства ---
    amount_: FloatProperty(
        name="Amount", default=0.1, min=0.0,
        description="Radius for fillet or distance for chamfer",
        update=CadQueryNode.process_node
    )
    segments_: IntProperty(
        name="Segments", default=1, min=1,
        description="Number of segments. 1 creates a chamfer (flat), >1 creates a fillet (rounded)",
        update=CadQueryNode.process_node
    )
    # Добавить выбор режима (Fillet/Chamfer)? Пока определяется сегментами.

    # --- Инициализация ---
    def sv_init(self, context):
        self.inputs.new(CQObjectSocket.bl_idname, "Object In")
        # Вход для селекторов (пока только ребра)
        self.inputs.new(CQSelectorSocket.bl_idname, "Selected Edges")
        self.inputs.new(CQNumberSocket.bl_idname, "Amount").prop_name = 'amount_'
        self.inputs.new(CQNumberSocket.bl_idname, "Segments").prop_name = 'segments_'
        self.outputs.new(CQObjectSocket.bl_idname, "Object Out")
        # Синхронизация UI сокетов
        try:
            self.inputs["Amount"].default_property = self.amount_
            self.inputs["Segments"].default_property = self.segments_
        except: pass

    # --- UI ---
    def draw_buttons(self, context, layout):
        super().draw_buttons(context, layout)
        # UI будет нарисовано сокетами

    # --- Обработка ---
    def process(self):
        socket_obj = self.inputs["Object In"]
        socket_sel = self.inputs["Selected Edges"]
        socket_amount = self.inputs["Amount"]
        socket_segments = self.inputs["Segments"]
        out_socket = self.outputs["Object Out"]


        if not socket_obj.is_linked:
            raise SocketConnectionError(self, "'Object In' must be connected")
        if not socket_sel.is_linked:
            # Если селектор не подключен, просто передаем объект дальше
            logger.debug(f"Node {self.name}: No edges selected, passing object through.")
            obj_in = socket_obj.sv_get() # Все равно нужно получить объект
            if obj_in is None: raise NodeProcessingError(self, "Input object is None")
            out_socket.sv_set(obj_in)
            return

        # Получаем данные
        try:
            obj_in = socket_obj.sv_get()
            selector_data = socket_sel.sv_get() if socket_sel.is_linked else None
            amount = socket_amount.sv_get() if socket_amount.is_linked else self.amount_
            segments = int(socket_segments.sv_get()) if socket_segments.is_linked else self.segments_

            if obj_in is None: raise NodeProcessingError(self, "Input object is None")
            if amount <= 0: raise NodeProcessingError(self, "Amount must be positive")
            if segments < 1: raise NodeProcessingError(self, "Segments must be 1 or greater")

            # Получаем Shape
            if isinstance(obj_in, cq.Workplane):
                solids = obj_in.solids().vals()
                if not solids: raise NodeProcessingError(self, "Input Workplane has no solids")
                shape_in = solids[0] # Работаем с первым солидом
                if len(solids) > 1: logger.warning(f"Node {self.name}: Input Workplane has multiple solids, applying bevel to the first one.")
            elif isinstance(obj_in, cq.Shape):
                shape_in = obj_in
            else:
                raise NodeProcessingError(self, f"Unsupported input object type: {type(obj_in)}")

            # Обрабатываем селектор (пока только один)
            edge_list = []
            if isinstance(selector_data, cq.Edge): # Проверяем тип напрямую
              edge_list.append(selector_data)
              logger.debug(f"Node {self.name}: Identified edge {selector_data} for beveling.")
            elif selector_data is not None:
              logger.warning(f"Node {self.name}: Received invalid selector data type: {type(selector_data)}. Expected cq.Edge.")

            if not edge_list:
                logger.debug(f"Node {self.name}: No valid edges selected for beveling. Passing original shape.")
                out_socket.sv_set(obj_in) # Передаем исходный объект
                return

        except Exception as e:
             if isinstance(e, (NodeProcessingError, SocketConnectionError)): raise
             else: raise NodeProcessingError(self, f"Input error: {e}")


        # Применяем фаску или скругление
        try:
            result_shape = None
            if segments == 1:
                # Chamfer
                logger.debug(f"Applying chamfer with distance {amount} to {len(edge_list)} edge(s).")
                result_shape = shape_in.chamfer(amount, amount, edge_list)
            else:
                logger.debug(f"Applying fillet with radius {amount} to edge(s): {edge_list}")
                result_shape = shape_in.fillet(amount, edge_list)

            if result_shape is None or not result_shape.isValid():
                 raise NodeProcessingError(self, "Bevel operation resulted in an invalid shape.")

            # Возвращаем результат как Shape (или обернуть в Workplane?)
            # Возвращаем Shape, чтобы не терять контекст, если вход был Shape
            out_socket.sv_set(result_shape)
            logger.debug(f"Node {self.name}: Bevel operation successful.")

        except Exception as e:
             raise NodeProcessingError(self, f"Bevel operation failed: {e}")


# --- Регистрация ---
classes = (
    BevelNode,
)