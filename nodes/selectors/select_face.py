# cadquery_parametric_addon/nodes/selectors/select_face.py
import bpy
from bpy.props import IntProperty
import logging

from ...core.node_tree import CadQueryNode
from ...core.sockets import CQObjectSocket, CQSelectorSocket, CQIntSocket # Используем IntSocket
from ...core.exceptions import NodeProcessingError, SocketConnectionError
from ...dependencies import cq

logger = logging.getLogger(__name__)

class SelectFaceNode(CadQueryNode):
    """Selects a specific face object from a CadQuery shape by its index."""
    bl_idname = 'CQPNode_SelectorSelectFaceNode'
    bl_label = 'Select Face'
    sv_category = 'Selectors'

    # --- Свойства ---
    index_: IntProperty(
        name="Index", default=0, min=0,
        description="Index of the face to select (starting from 0)",
        update=CadQueryNode.process_node
    )

    # --- Инициализация ---
    def sv_init(self, context):
        logger.debug(f"--- SelectFaceNode sv_init START for node {self.name} ---")
        try:
            self.inputs.new(CQObjectSocket.bl_idname, "Object In")
            socket_idx = self.inputs.new(CQIntSocket.bl_idname, "Index")
            socket_idx.prop_name = 'index_'
            socket_idx.default_property = self.index_
            self.outputs.new(CQObjectSocket.bl_idname, "Object Out")
            self.outputs.new(CQSelectorSocket.bl_idname, "Selected Face") # Передаем cq.Face
            logger.debug(f"  Created sockets and synced Index default: {socket_idx.default_property}")
        except Exception as e:
             logger.error(f"Error during socket creation/sync in {self.name}: {e}", exc_info=True)
        logger.debug(f"--- SelectFaceNode sv_init END ---")

    # --- UI ---
    def draw_buttons(self, context, layout):
        super().draw_buttons(context, layout) # Ошибка
        # Поле ввода индекса будет нарисовано сокетом

    # --- Обработка ---
    def process(self):
        socket_obj = self.inputs.get("Object In")
        socket_idx = self.inputs.get("Index")
        out_obj_socket = self.outputs.get("Object Out")
        out_sel_socket = self.outputs.get("Selected Face")

        if not all([socket_obj, socket_idx, out_obj_socket, out_sel_socket]):
            logger.warning(f"Node {self.name}: Sockets not fully initialized. Skipping."); return

        out_sel_socket.sv_set(None)
        selected_face_object = None
        obj_in = None

        try:
            if not socket_obj.is_linked:
                raise SocketConnectionError(self, "'Object In' must be connected")

            obj_in = socket_obj.sv_get()
            if socket_idx.is_linked:
                 index_val = socket_idx.sv_get(); index = int(round(index_val))
            else: index = self.index_
            if index < 0: index = 0

            if obj_in is None: raise NodeProcessingError(self, "Input object is None")

            current_shape = None
            if isinstance(obj_in, cq.Workplane):
                vals = obj_in.vals()
                if vals and isinstance(vals[0], cq.Shape): current_shape = vals[0]
                # if len(vals) > 1: logger.warning(...)
            elif isinstance(obj_in, cq.Shape):
                current_shape = obj_in
            else: raise NodeProcessingError(self, f"Unsupported input type: {type(obj_in)}")

            if not current_shape or not current_shape.isValid():
                 raise NodeProcessingError(self, "Input shape for face selection is invalid.")

            faces = current_shape.Faces()
            num_faces = len(faces)

            if num_faces == 0: logger.warning(f"Node {self.name}: Input shape has no faces.")
            elif not (0 <= index < num_faces): logger.warning(f"Node {self.name}: Index {index} out of bounds for faces (0-{num_faces-1}).")
            else:
                try: selected_face_object = faces[index] # Получаем cq.Face
                except Exception as e: logger.error(f"Failed to get face object at index {index}: {e}")

            out_sel_socket.sv_set(selected_face_object)
            out_obj_socket.sv_set(obj_in)

        except Exception as e:
            if out_sel_socket: out_sel_socket.sv_set(None)
            if out_obj_socket: out_obj_socket.sv_set(None)
            if isinstance(e, (NodeProcessingError, SocketConnectionError)): raise
            else:
                 logger.error(f"Error in SelectFaceNode process for node '{self.name}': {e}", exc_info=True)
                 raise NodeProcessingError(self, f"Processing failed: {e}")

# --- Регистрация ---
classes = (
    SelectFaceNode,
)