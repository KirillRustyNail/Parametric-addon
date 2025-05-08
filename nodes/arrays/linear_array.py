# cadquery_parametric_addon/nodes/arrays/linear_array.py
import bpy
from bpy.props import IntProperty, FloatProperty
import logging

from ...core.node_tree import CadQueryNode
from ...core.sockets import CQObjectSocket, CQNumberSocket, CQIntSocket
from ...core.exceptions import NodeProcessingError, SocketConnectionError
from ...dependencies import cq

logger = logging.getLogger(__name__)

class LinearArrayNode(CadQueryNode):
    """Creates a linear array of a CadQuery object by translating and uniting copies."""
    bl_idname = 'CQPNode_ArrayLinearArrayNode'
    bl_label = 'Linear Array'
    sv_category = 'Arrays'

    # --- Свойства Ноды ---
    count_x_: IntProperty( name="Count X", default=2, min=1, update=CadQueryNode.process_node )
    count_y_: IntProperty( name="Count Y", default=1, min=1, update=CadQueryNode.process_node )
    count_z_: IntProperty( name="Count Z", default=1, min=1, update=CadQueryNode.process_node )
    spacing_x_: FloatProperty( name="Spacing X", default=1.0, subtype='DISTANCE', unit='LENGTH', update=CadQueryNode.process_node )
    spacing_y_: FloatProperty( name="Spacing Y", default=1.0, subtype='DISTANCE', unit='LENGTH', update=CadQueryNode.process_node )
    spacing_z_: FloatProperty( name="Spacing Z", default=1.0, subtype='DISTANCE', unit='LENGTH', update=CadQueryNode.process_node )

    # --- Инициализация ---
    def sv_init(self, context):
        self.inputs.new(CQObjectSocket.bl_idname, "Object In")
        socket_cx = self.inputs.new(CQIntSocket.bl_idname, "Count X"); socket_cx.prop_name = 'count_x_'
        socket_cy = self.inputs.new(CQIntSocket.bl_idname, "Count Y"); socket_cy.prop_name = 'count_y_'
        socket_cz = self.inputs.new(CQIntSocket.bl_idname, "Count Z"); socket_cz.prop_name = 'count_z_'
        socket_sx = self.inputs.new(CQNumberSocket.bl_idname, "Spacing X"); socket_sx.prop_name = 'spacing_x_'
        socket_sy = self.inputs.new(CQNumberSocket.bl_idname, "Spacing Y"); socket_sy.prop_name = 'spacing_y_'
        socket_sz = self.inputs.new(CQNumberSocket.bl_idname, "Spacing Z"); socket_sz.prop_name = 'spacing_z_'
        self.outputs.new(CQObjectSocket.bl_idname, "Array Object")
        try: # Синхронизация UI сокетов
            socket_cx.default_property = self.count_x_; socket_cy.default_property = self.count_y_; socket_cz.default_property = self.count_z_
            socket_sx.default_property = self.spacing_x_; socket_sy.default_property = self.spacing_y_; socket_sz.default_property = self.spacing_z_
        except Exception as e: logger.error(f"Error syncing sockets in {self.name}: {e}")

    # --- UI ---
    def draw_buttons(self, context, layout):
        super().draw_buttons(context, layout) # Ошибки
        # Поля ввода рисуются сокетами

    # --- Обработка ---
    def process(self):
        logger.debug(f"--- LinearArrayNode process START for node {self.name} ---")
        socket_obj = self.inputs.get("Object In")
        if not socket_obj or not socket_obj.is_linked:
            # Очищаем выход, если вход не подключен
            self.outputs["Array Object"].sv_set(cq.Workplane("XY")) # Возвращаем пустой WP
            raise SocketConnectionError(self, "'Object In' must be connected")

        try:
            obj_in = socket_obj.sv_get()
            if obj_in is None: raise NodeProcessingError(self, "Input object is None")

            # --- Получение параметров ---
            count_x = int(round(self.inputs["Count X"].sv_get() if self.inputs["Count X"].is_linked else self.count_x_));
            count_y = int(round(self.inputs["Count Y"].sv_get() if self.inputs["Count Y"].is_linked else self.count_y_));
            count_z = int(round(self.inputs["Count Z"].sv_get() if self.inputs["Count Z"].is_linked else self.count_z_));
            spacing_x = self.inputs["Spacing X"].sv_get() if self.inputs["Spacing X"].is_linked else self.spacing_x_
            spacing_y = self.inputs["Spacing Y"].sv_get() if self.inputs["Spacing Y"].is_linked else self.spacing_y_
            spacing_z = self.inputs["Spacing Z"].sv_get() if self.inputs["Spacing Z"].is_linked else self.spacing_z_

            if count_x < 1: count_x = 1;
            if count_y < 1: count_y = 1;
            if count_z < 1: count_z = 1;
            total_elements = count_x * count_y * count_z
            if total_elements == 0 : raise NodeProcessingError(self, "Array count resulted in zero elements.") # Добавим ошибку

            logger.debug(f"  Params: Counts=({count_x},{count_y},{count_z}), Spacing=({spacing_x:.2f},{spacing_y:.2f},{spacing_z:.2f})")

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
            logger.debug(f"  Generating {total_elements} shapes for linear array...")
            for k in range(count_z):
                for j in range(count_y):
                    for i in range(count_x):
                        # Смещение относительно начала координат массива
                        offset_vec = cq.Vector(i * spacing_x, j * spacing_y, k * spacing_z)
                        # Если смещение нулевое (первый элемент), используем оригинал, иначе смещаем
                        if i == 0 and j == 0 and k == 0:
                             current_shape_to_add = input_shape_orig
                             # logger.debug(f"  Using original shape at offset {offset_vec.toTuple()}")
                        else:
                             translated_shape = input_shape_orig.translate(offset_vec)
                             if translated_shape and isinstance(translated_shape, cq.Shape) and translated_shape.isValid():
                                 current_shape_to_add = translated_shape
                                 # logger.debug(f"  Using translated shape at offset {offset_vec.toTuple()}")
                             else:
                                 logger.warning(f"  Translated shape for offset {offset_vec.toTuple()} is invalid or not a Shape.")
                                 current_shape_to_add = None # Пропускаем этот элемент

                        if current_shape_to_add:
                            shapes_to_union.append(current_shape_to_add)

            if not shapes_to_union:
                logger.warning("Linear array: No valid shapes were generated.")
                self.outputs["Array Object"].sv_set(cq.Workplane("XY")); return # Возвращаем пустой

            # --- Явно объединяем все Shape ---
            logger.debug(f"  Unioning {len(shapes_to_union)} shapes for linear array...")
            final_result_shape = shapes_to_union[0]
            if len(shapes_to_union) > 1:
                for i in range(1, len(shapes_to_union)):
                    try:
                        # logger.debug(f"    Fusing with shape {i}...")
                        # Используем fuse + clean для надежности
                        fused = final_result_shape.fuse(shapes_to_union[i])
                        cleaned = fused.clean()
                        if cleaned and cleaned.isValid(): final_result_shape = cleaned
                        elif fused and fused.isValid(): final_result_shape = fused; logger.warning("    fuse().clean() failed, using result of fuse()")
                        else: raise NodeProcessingError(self, f"Fuse/Clean failed for array element {i}")
                    except Exception as e_fuse:
                        logger.error(f"    Exception during fuse/clean for shape {i}: {e_fuse}", exc_info=True)
                        raise NodeProcessingError(self, f"Boolean fuse/clean failed for array element {i}: {e_fuse}")

            if not final_result_shape or not final_result_shape.isValid():
                 raise NodeProcessingError(self, "Union/Fuse of linear array elements resulted in invalid shape.")
            # --------------------------------

            result_wp = cq.Workplane("XY").add(final_result_shape) # Оборачиваем финальный ОДИН Shape
            self.outputs["Array Object"].sv_set(result_wp)
            logger.debug(f"Linear array created successfully. Output is Workplane.")

        except Exception as e:
            # Очищаем выход при ошибке
            self.outputs["Array Object"].sv_set(cq.Workplane("XY"))
            if isinstance(e, (NodeProcessingError, SocketConnectionError)): raise
            else:
                logger.error(f"Error in LinearArrayNode: {e}", exc_info=True)
                raise NodeProcessingError(self, f"Linear array failed: {e}")

# --- Регистрация ---
classes = (
    LinearArrayNode,
)