# cadquery_parametric_addon/nodes/operations/extrude_face.py
import bpy
from bpy.props import FloatProperty
import logging

from ...core.node_tree import CadQueryNode
from ...core.sockets import CQObjectSocket, CQSelectorSocket, CQNumberSocket
from ...core.exceptions import NodeProcessingError, SocketConnectionError
from ...dependencies import cq

logger = logging.getLogger(__name__)

class ExtrudeFaceNode(CadQueryNode):
    """Extrudes a selected face of a CadQuery object."""
    bl_idname = 'CQPNode_OperationExtrudeFaceNode'
    bl_label = 'Extrude Face'
    sv_category = 'Operations'

    # --- Свойства ---
    distance_: FloatProperty(
        name="Distance", default=1.0, subtype='DISTANCE', unit='LENGTH',
        description="Distance to extrude. Positive for outward, negative for inward.",
        update=CadQueryNode.process_node
    )
    # Можно добавить опцию "taper" (сужение/расширение)

    # --- Инициализация ---
    def sv_init(self, context):
        self.inputs.new(CQObjectSocket.bl_idname, "Object In")
        self.inputs.new(CQSelectorSocket.bl_idname, "Selected Face") # Ожидаем cq.Face
        self.inputs.new(CQNumberSocket.bl_idname, "Distance").prop_name = 'distance_'
        self.outputs.new(CQObjectSocket.bl_idname, "Object Out")

        try:
            self.inputs["Distance"].default_property = self.distance_
        except Exception as e: logger.error(f"Error syncing sockets in {self.name}: {e}")

    # --- UI ---
    def draw_buttons(self, context, layout):
        super().draw_buttons(context, layout)
        # Поле ввода будет нарисовано сокетом

    # --- Обработка ---
    def process(self):
        logger.debug(f"--- ExtrudeFaceNode process START for node {self.name} ---")
        socket_obj = self.inputs.get("Object In")
        socket_sel = self.inputs.get("Selected Face")
        socket_dist = self.inputs.get("Distance")
        out_socket = self.outputs.get("Object Out")

        if not all([socket_obj, socket_sel, socket_dist, out_socket]):
            logger.warning(f"Node {self.name}: Sockets not fully initialized. Skipping."); return

        obj_in_for_passthrough = None # Для передачи объекта, если операция не выполняется
        try:
            if socket_obj.is_linked:
                obj_in_for_passthrough = socket_obj.sv_get()
                if obj_in_for_passthrough is None:
                    raise NodeProcessingError(self, "Input object (for passthrough or processing) is None")
            else: raise SocketConnectionError(self, "'Object In' must be connected")

            if not socket_sel.is_linked:
                out_socket.sv_set(obj_in_for_passthrough) # Передаем исходный объект
                logger.debug(f"Node {self.name}: No face selected, passing object through.")
                return

            selected_cq_face = socket_sel.sv_get() # Это объект cq.Face
            distance = socket_dist.sv_get() if socket_dist.is_linked else self.distance_

            if selected_cq_face is None:
                logger.warning(f"Node {self.name}: No valid face selected. Passing original object.")
                out_socket.sv_set(obj_in_for_passthrough); return
            if not isinstance(selected_cq_face, cq.Face) or not selected_cq_face.isValid():
                raise NodeProcessingError(self, f"Selector input is not a valid CadQuery Face (type: {type(selected_cq_face)}).")

            # --- Получаем исходный Workplane (base_wp) для финальной булевой операции ---
            #    и исходный Shape (base_shape_for_op) для работы с ним.
            base_wp = None
            base_shape_for_op = None
            if isinstance(obj_in_for_passthrough, cq.Workplane):
                vals = obj_in_for_passthrough.vals()
                if vals and isinstance(vals[0], cq.Shape) and vals[0].isValid():
                    base_shape_for_op = vals[0]
                    base_wp = obj_in_for_passthrough # Сохраняем исходный WP
                else: raise NodeProcessingError(self, "Input Workplane is empty or invalid.")
            elif isinstance(obj_in_for_passthrough, cq.Shape):
                if not obj_in_for_passthrough.isValid(): raise NodeProcessingError(self, "Input Shape is invalid.")
                base_shape_for_op = obj_in_for_passthrough
                base_wp = cq.Workplane("XY").add(base_shape_for_op) # Оборачиваем в WP
            else:
                raise NodeProcessingError(self, f"Input object type {type(obj_in_for_passthrough)} not supported.")
            # ----------------------------------------------------------------------

            # --- Логика выдавливания выбранной грани ---
            final_result_wp = None
            if abs(distance) < 1e-6: # Если расстояние практически нулевое
                final_result_wp = base_wp # Возвращаем исходный Workplane
                logger.debug("Extrude distance is ~zero, returning original Workplane.")
            else:
                # 1. Получаем нормаль выбранной грани
                try:
                    # Для плоских граней нормаль одинакова в любой точке. Центр - хорошая точка.
                    face_normal = selected_cq_face.normalAt(selected_cq_face.Center())

                    if face_normal.Length < 1e-6 : raise ValueError("Face normal is a zero vector.")

                    logger.debug(f"  Selected Face Normal: {face_normal.toTuple()}")
                except Exception as e:
                    raise NodeProcessingError(self, f"Could not get normal of the selected face: {e}")

                try:
                    # Вектор выдавливания: нормаль * расстояние
                    # extrusion_vector = face_normal.multiply(distance)

                    extrude_distance = float(distance)

                    extruded_part_shape = cq.Solid.extrudeLinear(selected_cq_face, face_normal.multiply(extrude_distance))

                except Exception as e_extrude:
                    logger.error(f"cq.Solid.extrudeLinear failed: {e_extrude}", exc_info=True)
                    raise NodeProcessingError(self, f"Extrusion operation (extrudeLinear) failed: {e_extrude}")

                if not extruded_part_shape or not extruded_part_shape.isValid():
                    raise NodeProcessingError(self, "Extrusion (extrudeLinear) resulted in an invalid or empty shape.")
                # logger.debug(f"  Extruded part type: {type(extruded_part_shape)}")


                # 3. Булева операция между ИСХОДНЫМ Workplane (base_wp) и НОВЫМ телом (extruded_part_shape)
      
                if distance > 0: # Положительное значение - объединяем
                    final_result_wp = base_wp.union(extruded_part_shape)
                else: 
                    final_result_wp = base_wp.cut(extruded_part_shape)
                
            # --- Конец логики выдавливания ---

            if not final_result_wp: # На всякий случай
                 raise NodeProcessingError(self, "Final result Workplane is None after extrusion process.")

            out_socket.sv_set(final_result_wp) # Передаем Workplane дальше
            # logger.debug(f"Node {self.name}: Extrude operation successful. Output type: {type(final_result_wp)}")

        except Exception as e:
            if out_socket: out_socket.sv_set(None)
            if isinstance(e, (NodeProcessingError, SocketConnectionError)): raise
            else:
                logger.error(f"Error in ExtrudeFaceNode: {e}", exc_info=True)
                raise NodeProcessingError(self, f"Extrude face failed: {e}")


            
# --- Регистрация ---
classes = (
    ExtrudeFaceNode,
)