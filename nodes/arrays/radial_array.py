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
    """Creates a radial array of a CadQuery object by rotating and uniting copies."""
    bl_idname = 'CQPNode_ArrayRadialArrayNode'
    bl_label = 'Radial Array'
    sv_category = 'Arrays'

    # --- Свойства Ноды ---
    count_: IntProperty( name="Count", default=4, min=1, update=CadQueryNode.process_node )
    radius_: FloatProperty( name="Radius", default=1.0, min=0.0, subtype='DISTANCE', unit='LENGTH', update=CadQueryNode.process_node )
    angle_: FloatProperty( name="Total Angle", default=360.0, subtype='ANGLE', unit='ROTATION', update=CadQueryNode.process_node )

    # --- Инициализация ---
    def sv_init(self, context):
        self.inputs.new(CQObjectSocket.bl_idname, "Object In")
        socket_count = self.inputs.new(CQIntSocket.bl_idname, "Count"); socket_count.prop_name = 'count_'
        socket_radius = self.inputs.new(CQNumberSocket.bl_idname, "Radius"); socket_radius.prop_name = 'radius_'
        socket_angle = self.inputs.new(CQNumberSocket.bl_idname, "Total Angle (deg)"); socket_angle.prop_name = 'angle_'
        self.outputs.new(CQObjectSocket.bl_idname, "Array Object")
        try: # Синхронизация UI сокетов
            socket_count.default_property = self.count_
            socket_radius.default_property = self.radius_
            socket_angle.default_property = self.angle_
        except Exception as e: logger.error(f"Error syncing sockets in {self.name}: {e}")

    # --- UI ---
    def draw_buttons(self, context, layout):
        super().draw_buttons(context, layout) # Ошибки
        # Поля ввода рисуются сокетами

    # --- Обработка ---
    def process(self):
        logger.debug(f"--- RadialArrayNode process START for node {self.name} ---")
        socket_obj = self.inputs.get("Object In")
        if not socket_obj or not socket_obj.is_linked:
            self.outputs["Array Object"].sv_set(cq.Workplane("XY"))
            raise SocketConnectionError(self, "'Object In' must be connected")

        try:
            obj_in = socket_obj.sv_get()
            if obj_in is None: raise NodeProcessingError(self, "Input object is None")

            # --- Получение параметров ---
            count = int(round(self.inputs["Count"].sv_get() if self.inputs["Count"].is_linked else self.count_))
            radius = self.inputs["Radius"].sv_get() if self.inputs["Radius"].is_linked else self.radius_
            total_angle_deg = self.inputs["Total Angle (deg)"].sv_get() if self.inputs["Total Angle (deg)"].is_linked else self.angle_

            if count < 1: count = 1
            if radius < 0: radius = 0

            logger.debug(f"  Params: Count={count}, Radius={radius:.2f}, Angle={total_angle_deg:.1f} deg")

            # --- Получение исходной формы ---
            input_shape_orig = None
            if isinstance(obj_in, cq.Workplane):
                vals = obj_in.vals()
                if vals and isinstance(vals[0], cq.Shape): input_shape_orig = vals[0]
            elif isinstance(obj_in, cq.Shape):
                input_shape_orig = obj_in
            if not input_shape_orig or not input_shape_orig.isValid():
                raise NodeProcessingError(self, "Input object does not contain a valid Shape.")

            # --- Создаем список трансформированных Shape ---
            shapes_to_union = []
            logger.debug(f"  Generating {count} shapes for radial array...")

            if count == 1:
                transformed_shape = input_shape_orig
                if radius > 1e-6: # Смещаем, если радиус задан
                    angle_for_single_offset_deg = 0 # Обычно первый элемент на угле 0
                    x = radius * math.cos(math.radians(angle_for_single_offset_deg))
                    y = radius * math.sin(math.radians(angle_for_single_offset_deg))
                    offset_vec = cq.Vector(x, y, 0)
                    translated_shape = input_shape_orig.translate(offset_vec)
                    if translated_shape and translated_shape.isValid(): transformed_shape = translated_shape
                    else: logger.warning("Translate for count=1 failed.")
                if transformed_shape and transformed_shape.isValid(): shapes_to_union.append(transformed_shape)
            else: # count > 1
                angle_step_deg = total_angle_deg / count if count > 0 else 0
                for i in range(count):
                    current_angle_deg = i * angle_step_deg
                    current_angle_rad = math.radians(current_angle_deg)
                    x = radius * math.cos(current_angle_rad)
                    y = radius * math.sin(current_angle_rad)

                    # Применяем трансформации к копии исходной формы
                    # Сначала поворот вокруг Z, потом смещение
                    try:
                        # .copy() не нужно, операции возвращают новые объекты
                        rotated_shape = input_shape_orig.rotate((0,0,0), (0,0,1), current_angle_deg)
                        if not rotated_shape or not rotated_shape.isValid(): raise ValueError("Rotation failed")
                        translated_shape = rotated_shape.translate((x,y,0))
                        if not translated_shape or not translated_shape.isValid(): raise ValueError("Translation failed")
                        shapes_to_union.append(translated_shape)
                        # logger.debug(f"    Generated shape for angle {current_angle_deg:.1f}")
                    except Exception as e_trf:
                        logger.warning(f"    Transformation failed for item {i} in radial array: {e_trf}")


            if not shapes_to_union:
                logger.warning("Radial array: No valid shapes were generated.")
                self.outputs["Array Object"].sv_set(cq.Workplane("XY")); return

            # --- Явно объединяем все Shape ---
            logger.debug(f"  Unioning {len(shapes_to_union)} shapes for radial array...")
            final_result_shape = shapes_to_union[0]
            if len(shapes_to_union) > 1:
                for i in range(1, len(shapes_to_union)):
                    try:
                        # logger.debug(f"    Fusing with shape {i}...")
                        fused = final_result_shape.fuse(shapes_to_union[i])
                        cleaned = fused.clean()
                        if cleaned and cleaned.isValid(): final_result_shape = cleaned
                        elif fused and fused.isValid(): final_result_shape = fused; logger.warning("    fuse().clean() failed, using result of fuse()")
                        else: raise NodeProcessingError(self, f"Fuse/Clean failed for array element {i}")
                    except Exception as e_fuse:
                        logger.error(f"    Exception during fuse/clean for shape {i}: {e_fuse}", exc_info=True)
                        raise NodeProcessingError(self, f"Boolean fuse/clean failed for array element {i}: {e_fuse}")

            if not final_result_shape or not final_result_shape.isValid():
                 raise NodeProcessingError(self, "Union/Fuse of radial array elements resulted in invalid shape.")
            # --------------------------------

            result_wp = cq.Workplane("XY").add(final_result_shape) # Оборачиваем финальный ОДИН Shape
            self.outputs["Array Object"].sv_set(result_wp)
            logger.debug(f"Radial array created successfully. Output is Workplane.")

        except Exception as e:
            self.outputs["Array Object"].sv_set(cq.Workplane("XY")) # Очищаем выход при ошибке
            if isinstance(e, (NodeProcessingError, SocketConnectionError)): raise
            else:
                logger.error(f"Error in RadialArrayNode: {e}", exc_info=True)
                raise NodeProcessingError(self, f"Radial array failed: {e}")

# --- Регистрация ---
classes = (
    RadialArrayNode,
)