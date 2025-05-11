# cadquery_parametric_addon/nodes/io/marker_display.py
import bpy
from bpy.props import (
    StringProperty, FloatProperty, FloatVectorProperty, BoolProperty,
    EnumProperty, CollectionProperty
)
import logging

from ...core.node_tree import CadQueryNode
from ...core.sockets import CQObjectSocket, CQSelectorSocket # Принимаем геометрию и селекторы
from ...core.exceptions import NodeProcessingError, SocketConnectionError
from ...dependencies import cq # Нужен для типов Vertex, Edge, Face

logger = logging.getLogger(__name__)

# Типы маркеров, соответствующие bpy.types.Object.empty_display_type + CUBE/SPHERE
MARKER_TYPES = [ # Список остается прежним
    ('PLAIN_AXES', "Axes", "Display marker as axes", 'EMPTY_AXIS', 0),
    ('ARROWS', "Arrows", "Display marker as arrows", 'EMPTY_ARROWS', 1),
    ('SINGLE_ARROW', "Single Arrow", "Display marker as single arrow", 'EMPTY_SINGLE_ARROW', 2),
    ('CIRCLE', "Circle", "Display marker as circle", 'VIEW3D_CURSOR', 3),
    ('CUBE', "Cube", "Display marker as cube", 'MESH_CUBE', 4),
    ('SPHERE', "Sphere", "Display marker as sphere (Icosphere)", 'MESH_ICOSPHERE', 5),
    ('IMAGE', "Image", "Display marker as image (not useful here)", 'IMAGE_PLANE', 7)
]

# --- Нода ---
class MarkerDisplayNode(CadQueryNode):
    """Displays visual markers in the 3D View for selected CQ elements."""
    bl_idname = 'CQPNode_IOMarkerDisplayNode'
    bl_label = 'Marker Display'
    sv_category = 'Input/Output' # Или новая категория 'Visualization'?

    # --- Свойства ---
    enabled_: BoolProperty( name="Enabled", default=True, update=CadQueryNode.process_node )
    marker_type_: EnumProperty( items=MARKER_TYPES, name="Marker Type", default='CUBE', update=CadQueryNode.process_node )
    marker_size_: FloatProperty( name="Size", default=0.05, min=0.001, subtype='DISTANCE', unit='LENGTH', update=CadQueryNode.process_node )
    marker_color_: FloatVectorProperty( name="Color", default=(0.1, 1.0, 0.1, 0.8), min=0.0, max=1.0, size=4, subtype='COLOR', update=CadQueryNode.process_node )
    marker_names: CollectionProperty(type=bpy.types.PropertyGroup)

    # --- Внутреннее хранилище имен маркеров ---
    # Используем CollectionProperty для хранения строк - имен созданных объектов
    # Это не самый эффективный способ, но он работает и сохраняется с файлом.
    # Альтернатива - использовать IDProperty на ноде (менее удобно для списка).
    marker_names: CollectionProperty(type=bpy.types.PropertyGroup) # Будем хранить строки в name элемента

    # --- Инициализация ---
    def sv_init(self, context):
        self.inputs.new(CQObjectSocket.bl_idname, "Geometry") # Геометрия, на которой искать элементы
        self.inputs.new(CQSelectorSocket.bl_idname, "Selectors") # Выбранные элементы (cq.Vertex/Edge/Face или список)
        # Нет выходов

    # --- UI ---
    def draw_buttons(self, context, layout):
        super().draw_buttons(context, layout)
        col = layout.column(align=True)
        row = col.row(align=True)
        row.prop(self, "enabled_", text="", icon='CHECKBOX_HLT' if self.enabled_ else 'CHECKBOX_DEHLT', toggle=True)
        row.prop(self, "marker_type_", text="")
        row = col.row(align=True)
        row.prop(self, "marker_size_")
        row.prop(self, "marker_color_", text="")

    # --- Очистка ---
    def clear_markers(self):
        """Removes all markers previously created by this node."""
        # logger.debug(f"Node {self.name}: Clearing markers...")
        removed_count = 0
        # Итерируемся по КОПИИ имен, так как будем удалять элементы из коллекции
        names_to_remove = [item.name for item in self.marker_names]
        for marker_name in names_to_remove:
            if marker_name and marker_name in bpy.data.objects:
                 try:
                      bpy.data.objects.remove(bpy.data.objects[marker_name], do_unlink=True)
                      removed_count += 1
                 except Exception as e:
                      logger.error(f"Failed to remove marker '{marker_name}': {e}")
            else:
                 # Имя есть в списке, но объекта нет - просто удаляем из списка
                 pass # Удаление из CollectionProperty произойдет ниже

        # Очищаем саму коллекцию свойств
        if self.marker_names: # Проверяем, есть ли что чистить
            self.marker_names.clear()
            # logger.debug(f"Removed {removed_count} marker objects and cleared marker_names collection.")

    def sv_free(self):
        """Called when node is removed."""
        self.clear_markers()

    # --- Обработка ---
    def process(self):
        # 1. Очистить старые маркеры
        self.clear_markers()

        is_enabled = self.enabled_
        marker_type = self.marker_type_
        marker_size = self.marker_size_
        marker_color = tuple(self.marker_color_)

        # 2. Проверить входы и флаг Enabled
        socket_geo = self.inputs["Geometry"]
        socket_sel = self.inputs["Selectors"]
        
        if not self.enabled_ or not socket_geo.is_linked or not socket_sel.is_linked:
            # logger.debug(f"Node {self.name}: Skipping marker creation (disabled or inputs not linked).")
            return

        # --- Получаем значения свойств ноды  ---

        # marker_type = self.marker_type_
        # marker_size = self.marker_size_
        # marker_color = tuple(self.marker_color_) # Получаем цвет как tuple
        # -------------------------------------------

        # 3. Получить данные
        try:
            #obj_in = socket_geo.sv_get()
            selector_in = socket_sel.sv_get() # Ожидаем cq.Vertex/Edge/Face или список таких объектов
            #if obj_in is None: raise NodeProcessingError(self, "Input Geometry is None")
            if selector_in is None: logger.debug(f"Node {self.name}: No selector data."); return
        except Exception as e:
            raise NodeProcessingError(self, f"Input error: {e}")

        
        # 5. Подготовить список селекторов (всегда список)
        selectors = []
        if isinstance(selector_in, list): selectors = selector_in
        elif isinstance(selector_in, (cq.Vertex, cq.Edge, cq.Face)): selectors = [selector_in]
        else: logger.warning(f"Node {self.name}: Invalid selector type: {type(selector_in)}."); return

        # 6. Итерация и создание маркеров
        # logger.debug(f"Node {self.name}: Processing {len(selectors)} selectors...")
        context = bpy.context

        if not context.collection: logger.error("No active collection for markers."); return

        collection = context.collection 
        created_count = 0
        base_name = f"Marker_{self.id_data.name}_{self.name}"

        for i, sel in enumerate(selectors):
            points_to_mark = []
            if isinstance(sel, cq.Vertex):
                 try: points_to_mark.append(sel.toTuple())
                 except: logger.warning(f"Could not get coordinates for Vertex selector {i}")
            elif isinstance(sel, cq.Edge):
                 try:
                      points_to_mark.append(sel.startPoint().toTuple())
                      points_to_mark.append(sel.endPoint().toTuple())
                 except: logger.warning(f"Could not get coordinates for Edge selector {i}")
            elif isinstance(sel, cq.Face):
                try:
                    # Получаем центр грани
                    center_pt = sel.Center()
                    points_to_mark.append(center_pt.toTuple())
                except Exception as e_face:
                    logger.warning(f"Could not get center for Face selector {i}: {e_face}")

            # Создаем маркеры для найденных точек
            for point_idx, loc in enumerate(points_to_mark):
                try:
                    marker_name = f"{base_name}_{i}_{point_idx}"
                    marker = None; is_mesh_marker = False
                    if marker_type in {'CUBE', 'SPHERE'}:
                        is_mesh_marker = True
                        current_active = context.view_layer.objects.active
                        bpy.ops.object.select_all(action='DESELECT')

                        if marker_type == 'CUBE': bpy.ops.mesh.primitive_cube_add(size=marker_size, location=loc)
                        else: bpy.ops.mesh.primitive_ico_sphere_add(radius=marker_size/2.0, subdivisions=1, location=loc) # Уменьшил subdivisions
                        
                        marker = context.view_layer.objects.active
                        if not marker: raise RuntimeError("Failed to get created mesh primitive.")
                        marker.name = marker_name
                        
                        mat_rgba = marker_color
                        mat_name = f"CQMarkerMat_{mat_rgba[0]:.2f}_{mat_rgba[1]:.2f}_{mat_rgba[2]:.2f}_{mat_rgba[3]:.2f}"
                        marker_mat = bpy.data.materials.get(mat_name)
                        
                        if not marker_mat:
                            marker_mat = bpy.data.materials.new(name=mat_name)
                            marker_mat.use_nodes = True # Используем ноды
                            nodes = marker_mat.node_tree.nodes
                            links = marker_mat.node_tree.links
                            # Ищем ноду Principled BSDF или создаем ее
                            bsdf = nodes.get("Principled BSDF")
                            if not bsdf: # Если нет стандартной, создаем (маловероятно)
                                bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
                                # Позиционируем ее (не обязательно)
                                bsdf.location = 0,0
                                # Если создали BSDF, нужно связать ее с выходом
                                output_node = nodes.get("Material Output")
                                if not output_node: output_node = nodes.new(type='ShaderNodeOutputMaterial')
                                output_node.location = 200, 0
                                links.new(bsdf.outputs['BSDF'], output_node.inputs['Surface'])

                            # Устанавливаем цвет и альфу
                            if bsdf:
                                    bsdf.inputs["Base Color"].default_value = mat_rgba # Передаем RGBA
                                    # Для прозрачности в Eevee/Cycles нужно настроить Blend Mode
                                    marker_mat.blend_method = 'BLEND' # или 'HASHED'
                                    marker_mat.shadow_method = 'HASHED' # или 'NONE'
                                    # Также можно настроить другие параметры BSDF, если нужно
                                    bsdf.inputs["Roughness"].default_value = 0.8
                                    bsdf.inputs["Metallic"].default_value = 0.1
                                    marker_mat.diffuse_color = mat_rgba # RGBA

                        
                        
                        
                        if marker.data.materials: marker.data.materials[0] = marker_mat
                        else: marker.data.materials.append(marker_mat)
                        
                        bpy.context.view_layer.objects.active = current_active

                    else: # Empty
                        marker = bpy.data.objects.new(marker_name, None)
                        marker.location = loc
                        marker.empty_display_size = marker_size
                        marker.empty_display_type = marker_type
                        marker.color = marker_color # Для Empty цвет устанавливается так
                        collection.objects.link(marker)

                    item = self.marker_names.add(); item.name = marker.name
                    created_count += 1
                except Exception as e_create:
                    logger.error(f"Failed to create marker at {loc} for selector {i}: {e_create}", exc_info=True)
                    if marker and marker.name in bpy.data.objects:
                        try: bpy.data.objects.remove(marker, do_unlink=True)
                        except: pass


# --- Регистрация ---
classes = (
    MarkerDisplayNode,
)