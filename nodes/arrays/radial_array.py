# cadquery_parametric_addon/nodes/arrays/radial_array.py
import bpy
from bpy.props import IntProperty, FloatProperty
import math
import logging

from ...core.node_tree import CadQueryNode
from ...core.sockets import CQObjectSocket, CQNumberSocket, CQIntSocket
from ...core.exceptions import NodeProcessingError, SocketConnectionError
from ...dependencies import cq

logger = logging.getLogger(__name__)

class RadialArrayNode(CadQueryNode):
    """Creates a radial array of a CadQuery object."""
    bl_idname = 'CQPNode_ArrayRadialArrayNode'
    bl_label = 'Radial Array'
    sv_category = 'Arrays'

    count_: IntProperty( name="Count", default=4, min=1, update=CadQueryNode.process_node )
    radius_: FloatProperty( name="Radius", default=1.0, min=0.0, subtype='DISTANCE', unit='LENGTH', update=CadQueryNode.process_node )
    angle_: FloatProperty( name="Total Angle", default=360.0, subtype='ANGLE', unit='ROTATION', update=CadQueryNode.process_node )

    def sv_init(self, context):
        self.inputs.new(CQObjectSocket.bl_idname, "Object In")
        socket_count = self.inputs.new(CQIntSocket.bl_idname, "Count"); socket_count.prop_name = 'count_'
        socket_radius = self.inputs.new(CQNumberSocket.bl_idname, "Radius"); socket_radius.prop_name = 'radius_'
        socket_angle = self.inputs.new(CQNumberSocket.bl_idname, "Total Angle (deg)"); socket_angle.prop_name = 'angle_'
        self.outputs.new(CQObjectSocket.bl_idname, "Array Object")
        try:
            socket_count.default_property = self.count_
            socket_radius.default_property = self.radius_
            socket_angle.default_property = self.angle_
        except Exception as e: logger.error(f"Error syncing sockets in {self.name}: {e}")

    def draw_buttons(self, context, layout):
        super().draw_buttons(context, layout)

    def process(self):
        socket_obj = self.inputs.get("Object In")
        if not socket_obj or not socket_obj.is_linked:
            raise SocketConnectionError(self, "'Object In' must be connected")

        try:
            obj_in = socket_obj.sv_get()
            if obj_in is None: raise NodeProcessingError(self, "Input object is None")

            # ... (получение count, radius, total_angle_deg) ...
            count = int(round(self.inputs["Count"].sv_get() if self.inputs["Count"].is_linked else self.count_))
            radius = self.inputs["Radius"].sv_get() if self.inputs["Radius"].is_linked else self.radius_
            total_angle_deg = self.inputs["Total Angle (deg)"].sv_get() if self.inputs["Total Angle (deg)"].is_linked else self.angle_

            if count < 1: count = 1
            if radius < 0: radius = 0

            input_shape = None
            if isinstance(obj_in, cq.Workplane):
                vals = obj_in.vals()
                if vals and isinstance(vals[0], cq.Shape): input_shape = vals[0]
            elif isinstance(obj_in, cq.Shape):
                input_shape = obj_in
            if not input_shape or not input_shape.isValid():
                raise NodeProcessingError(self, "Input object does not contain a valid Shape.")

            # --- Создаем радиальный массив через Workplane.add() ---
            result_wp = cq.Workplane("XY") # Начинаем с пустого Workplane
            added_at_least_one = False

            if count == 1:
                transformed_shape = input_shape # По умолчанию не трансформируем для count=1
                if radius > 1e-6: # Смещаем, если радиус задан
                    # Угол для одного элемента обычно 0, если total_angle не указан как-то специально
                    # Смещаем по X, если total_angle_deg = 0 или 360
                    angle_for_single_offset_deg = 0
                    # if total_angle_deg != 0 and total_angle_deg != 360:
                        # Можно взять половину угла, если хотим центрировать один элемент в секторе
                        # angle_for_single_offset_deg = total_angle_deg / 2.0

                    x = radius * math.cos(math.radians(angle_for_single_offset_deg))
                    y = radius * math.sin(math.radians(angle_for_single_offset_deg))
                    offset_vec = cq.Vector(x, y, 0)
                    # logger.debug(f"Radial array count=1: offsetting by {offset_vec.toTuple()}")
                    transformed_shape = input_shape.translate(offset_vec)

                if transformed_shape and transformed_shape.isValid():
                    result_wp = result_wp.add(transformed_shape)
                    added_at_least_one = True

            else: # count > 1
                angle_step_deg = total_angle_deg / count if count > 0 else 0
                for i in range(count):
                    current_angle_deg = i * angle_step_deg
                    current_angle_rad = math.radians(current_angle_deg)

                    x = radius * math.cos(current_angle_rad)
                    y = radius * math.sin(current_angle_rad)

                    # Создаем временный Workplane, трансформируем его СК, затем добавляем input_shape
                    item_wp = (
                        cq.Workplane("XY")
                        .transformed(offset=(x, y, 0), rotate=(0, 0, current_angle_deg))
                        .add(input_shape) # Добавляем исходную форму в трансформированную СК
                    )
                    item_shapes = item_wp.vals()
                    if item_shapes and isinstance(item_shapes[0], cq.Shape) and item_shapes[0].isValid():
                        # Добавляем полученный Shape (или первый Shape из Workplane) в result_wp
                        result_wp = result_wp.add(item_shapes[0])
                        added_at_least_one = True
                    # else:
                        # logger.warning(f"Transformation resulted in invalid shape for item {i} in radial array.")


            if not added_at_least_one:
                 logger.warning("Radial array: No valid shapes were added to the array.")
                 self.outputs["Array Object"].sv_set(cq.Workplane("XY"))
                 return

            if not result_wp.vals() or not result_wp.vals()[0].isValid():
                 logger.warning("Radial array resulted in an empty or invalid Workplane.")
                 self.outputs["Array Object"].sv_set(cq.Workplane("XY"))
                 return

            self.outputs["Array Object"].sv_set(result_wp)
            # logger.debug(f"Radial array created. Result type: {type(result_wp)}")

        except Exception as e:
            if isinstance(e, (NodeProcessingError, SocketConnectionError)): raise
            else:
                logger.error(f"Error in RadialArrayNode: {e}", exc_info=True)
                raise NodeProcessingError(self, f"Radial array failed: {e}")

# --- Регистрация ---
classes = (
    RadialArrayNode,
)