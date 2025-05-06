# cadquery_parametric_addon/nodes/arrays/linear_array.py
import bpy
from bpy.props import IntProperty, FloatProperty, FloatVectorProperty
import logging

from ...core.node_tree import CadQueryNode
from ...core.sockets import CQObjectSocket, CQNumberSocket, CQIntSocket, CQVectorSocket
from ...core.exceptions import NodeProcessingError, SocketConnectionError
from ...dependencies import cq

logger = logging.getLogger(__name__)

class LinearArrayNode(CadQueryNode):
    """Creates a linear array of a CadQuery object."""
    bl_idname = 'CQPNode_ArrayLinearArrayNode'
    bl_label = 'Linear Array'
    sv_category = 'Arrays' # Новая категория

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
        # Сокеты для управления через другие ноды
        self.inputs.new(CQIntSocket.bl_idname, "Count X").prop_name = 'count_x_'
        self.inputs.new(CQIntSocket.bl_idname, "Count Y").prop_name = 'count_y_'
        self.inputs.new(CQIntSocket.bl_idname, "Count Z").prop_name = 'count_z_'
        self.inputs.new(CQNumberSocket.bl_idname, "Spacing X").prop_name = 'spacing_x_'
        self.inputs.new(CQNumberSocket.bl_idname, "Spacing Y").prop_name = 'spacing_y_'
        self.inputs.new(CQNumberSocket.bl_idname, "Spacing Z").prop_name = 'spacing_z_'
        self.outputs.new(CQObjectSocket.bl_idname, "Array Object")

        # Синхронизация UI сокетов
        try:
            self.inputs["Count X"].default_property = self.count_x_
            self.inputs["Count Y"].default_property = self.count_y_
            self.inputs["Count Z"].default_property = self.count_z_
            self.inputs["Spacing X"].default_property = self.spacing_x_
            self.inputs["Spacing Y"].default_property = self.spacing_y_
            self.inputs["Spacing Z"].default_property = self.spacing_z_
        except Exception as e: logger.error(f"Error syncing sockets in {self.name}: {e}")

    # --- UI ---
    def draw_buttons(self, context, layout):
        super().draw_buttons(context, layout)
        # Поля ввода будут нарисованы сокетами, если не подключены

    # --- Обработка ---
    def process(self):
        logger.debug(f"--- LinearArrayNode process START for node {self.name} ---")
        socket_obj = self.inputs.get("Object In")
        if not socket_obj or not socket_obj.is_linked:
            raise SocketConnectionError(self, "'Object In' must be connected")

        try:
            obj_in = socket_obj.sv_get()
            if obj_in is None: raise NodeProcessingError(self, "Input object is None")

            # Получение параметров
            count_x = int(round(self.inputs["Count X"].sv_get() if self.inputs["Count X"].is_linked else self.count_x_))
            count_y = int(round(self.inputs["Count Y"].sv_get() if self.inputs["Count Y"].is_linked else self.count_y_))
            count_z = int(round(self.inputs["Count Z"].sv_get() if self.inputs["Count Z"].is_linked else self.count_z_))
            spacing_x = self.inputs["Spacing X"].sv_get() if self.inputs["Spacing X"].is_linked else self.spacing_x_
            spacing_y = self.inputs["Spacing Y"].sv_get() if self.inputs["Spacing Y"].is_linked else self.spacing_y_
            spacing_z = self.inputs["Spacing Z"].sv_get() if self.inputs["Spacing Z"].is_linked else self.spacing_z_

            logger.debug(f"  Process count_x: {self.count_x_}")
            logger.debug(f"  Process count_y: {self.count_y_}")
            logger.debug(f"  Process count_z: {self.count_z_}")

            logger.debug(f"  Process spacing_x: {self.spacing_x_}")
            logger.debug(f"  Process spacing_y: {self.spacing_y_}")
            logger.debug(f"  Process spacing_z: {self.spacing_z_}")

            if count_x < 1: count_x = 1
            if count_y < 1: count_y = 1
            if count_z < 1: count_z = 1

            logger.debug(f"  Params: Counts=({count_x},{count_y},{count_z}), Spacing=({spacing_x:.2f},{spacing_y:.2f},{spacing_z:.2f})")

            input_shape_orig = None # Исходная форма для копирования
            if isinstance(obj_in, cq.Workplane):
                vals = obj_in.vals()
                if vals and isinstance(vals[0], cq.Shape): input_shape_orig = vals[0]
            elif isinstance(obj_in, cq.Shape):
                input_shape_orig = obj_in
            if not input_shape_orig or not input_shape_orig.isValid():
                raise NodeProcessingError(self, "Input object does not contain a valid Shape.")

            # --- Создаем линейный массив через Workplane.add() ---
            # Начинаем с пустого Workplane, если массив будет содержать > 1 элемента,
            # или с Workplane, содержащего исходный элемент, если массив 1x1x1.
            result_wp = cq.Workplane("XY")
            total_elements = count_x * count_y * count_z
            added_shapes_count = 0

            if total_elements == 0 : # На случай, если count может быть 0 (хотя мы ставим min=1)
                 logger.warning("Linear array: Total elements count is zero.")
                 self.outputs["Array Object"].sv_set(cq.Workplane("XY")); return

            # logger.debug(f"  Total elements to generate: {total_elements}")

            for k in range(count_z):
                for j in range(count_y):
                    for i in range(count_x):
                        # Если это первый элемент (0,0,0) и это единственный элемент в массиве,
                        # то input_shape_orig уже будет им.
                        # Если элементов много, то input_shape_orig будет добавлен первым.
                        # Если это не первый элемент (i,j,k != 0,0,0), то мы смещаем input_shape_orig.

                        # Создаем копию исходной формы для каждой итерации, КРОМЕ первой (0,0,0)
                        # если мы хотим, чтобы исходный объект был первым элементом
                        current_shape_to_add = None
                        offset_vec = cq.Vector(i * spacing_x, j * spacing_y, k * spacing_z)

                        if i == 0 and j == 0 and k == 0:
                             # Для самого первого элемента используем оригинальную форму
                             current_shape_to_add = input_shape_orig
                             # logger.debug(f"  Adding original shape at offset {offset_vec.toTuple()}")
                        else:
                             # Для последующих элементов создаем смещенную копию
                             # .copy() может быть не нужно, т.к. translate() возвращает новый объект
                             translated_shape = input_shape_orig.translate(offset_vec)
                             if translated_shape and translated_shape.isValid():
                                 current_shape_to_add = translated_shape
                                 # logger.debug(f"  Adding translated shape at offset {offset_vec.toTuple()}")
                             # else:
                                 # logger.warning(f"  Translated shape for offset {offset_vec.toTuple()} is invalid.")

                        if current_shape_to_add:
                            # logger.debug(f"    Adding shape to result_wp. Current stack depth: {len(result_wp.objects)}")
                            result_wp = result_wp.add(current_shape_to_add) # Workplane.add() должен объединять
                            added_shapes_count += 1
                            # logger.debug(f"    Shape added. New stack depth: {len(result_wp.objects)}")
                        # else:
                            # logger.warning(f"  current_shape_to_add is None for i,j,k = ({i},{j},{k})")


            logger.debug(f"  Total shapes added to Workplane before final check: {added_shapes_count}")

            if added_shapes_count == 0:
                 logger.warning("Linear array: No valid shapes were actually added to the array.")
                 self.outputs["Array Object"].sv_set(cq.Workplane("XY")); return

            # Проверяем результат
            final_vals = result_wp.vals()
            if not final_vals or not final_vals[0].isValid():
                 logger.warning(f"Linear array resulted in an empty or invalid Workplane. Shapes on stack: {len(result_wp.objects)}")
                 self.outputs["Array Object"].sv_set(cq.Workplane("XY")); return

            # logger.debug(f"  Final result Workplane has {len(final_vals)} solid(s) after all adds.")
            self.outputs["Array Object"].sv_set(result_wp)
            logger.debug(f"Linear array created. Result type: {type(result_wp)}")

        except Exception as e:
            if isinstance(e, (NodeProcessingError, SocketConnectionError)): raise
            else:
                logger.error(f"Error in LinearArrayNode: {e}", exc_info=True)
                raise NodeProcessingError(self, f"Linear array failed: {e}")

# --- Регистрация ---
classes = (
    LinearArrayNode,
)