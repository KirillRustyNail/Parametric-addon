# cadquery_parametric_addon/nodes/io/viewer.py
import bpy
from bpy.props import StringProperty, FloatProperty, BoolProperty # Добавляем FloatProperty
import logging
import math # Нужен для передачи градусов в оператор

from ...core.node_tree import CadQueryNode
from ...core.sockets import CQObjectSocket, CQNumberSocket # Добавляем CQNumberSocket
from ...utils import cq_utils
from ...core.exceptions import NodeProcessingError, ViewerError, SocketConnectionError
from ...dependencies import cq

logger = logging.getLogger(__name__)

# --- Операторы для кнопок (перемещены сюда или импортированы из operators.process_mesh) ---
# Лучше импортировать, но для полноты файла можно определить здесь временно
# Если импортируете, убедитесь, что оператор зарегистрирован ДО ноды
try:
    # Пытаемся импортировать, если он в отдельном файле
    from ...operators.process_mesh import CQP_OT_ProcessMeshOp
except ImportError:
    logger.warning("CQP_OT_ProcessMeshOp not found in operators.process_mesh. Buttons might not work.")
    # Определяем заглушку, чтобы код не падал
    class CQP_OT_ProcessMeshOp: pass


# --- Нода ---
class CQViewerNode(CadQueryNode): # Переименовали класс
    """Displays the result of a CadQuery operation in the Blender scene
       and provides mesh processing options."""
    bl_idname = 'CQPNode_IOCQViewerNode' # Новый ID
    bl_label = 'Viewer'
    sv_category = 'Input/Output'

    # --- Свойства ---
    target_object_name: StringProperty(
        name="Target Object Name",
        description="Name of the Blender object created/updated by this node",
        default=""
    )

    # --- Свойство для точности ---
    tessellation_tolerance_: FloatProperty(
        name="Tolerance", default=0.1, min=0.001, max=1.0, precision=3,
        subtype='FACTOR', # Factor удобнее для диапазона 0-1
        description="Tessellation tolerance (smaller = higher detail)",
        update=CadQueryNode.process_node
    )
    # --- Свойство для угловой точности ---
    tessellation_angular_: FloatProperty(
        name="Angular Tol.", default=0.1, min=0.01, max=1.0, precision=2,
        subtype='FACTOR',
        description="Tessellation angular tolerance (smaller = higher detail on curves)",
        update=CadQueryNode.process_node
    )

    # --- Инициализация ---
    def sv_init(self, context):
        self.inputs.new(CQObjectSocket.bl_idname, "Object In")
        # --- Добавляем сокеты для управления точностью ---
        socket_tol = self.inputs.new(CQNumberSocket.bl_idname, "Tolerance").prop_name = 'tessellation_tolerance_'
        socket_ang = self.inputs.new(CQNumberSocket.bl_idname, "Angular Tol.").prop_name = 'tessellation_angular_'
    
        try:
            socket_tol.inputs['Tolerance'].default_property = self.tessellation_tolerance_
            socket_ang.inputs['Angular Tol.'].default_property = self.tessellation_angular_
        except Exception as e:
            logger.error(f"Error syncing tolerance sockets in {self.name}: {e}")
        # ---------------------------------

    # --- UI ---
    def draw_buttons(self, context, layout):
        super().draw_buttons(context, layout) # Ошибки
        layout.prop(self, "target_object_name", text="Output Name")

        # --- Кнопки для операторов ---
        layout.separator()
        col_ops = layout.column(align=True)
        col_ops.label(text="Mesh Ops:")

        can_process_flag = False # По умолчанию False
        obj_name_to_check = self.target_object_name
        if isinstance(obj_name_to_check, str) and obj_name_to_check: # Проверяем, что это строка и она не пустая
            if obj_name_to_check in bpy.data.objects:
                can_process_flag = True

        row_merge = col_ops.row(align=True)
        row_merge.enabled = can_process_flag # Используем новый флаг
        op_merge = row_merge.operator("cqp.process_mesh_op", text="Merge by Distance", icon='AUTOMERGE_ON')
        op_merge.node_path = self.get_path(); op_merge.operation = 'MERGE'

        row_quads = col_ops.row(align=True)
        row_quads.enabled = can_process_flag # Используем новый флаг
        op_quads = row_quads.operator("cqp.process_mesh_op", text="Tris to Quads", icon='MOD_TRIANGULATE')
        op_quads.node_path = self.get_path(); op_quads.operation = 'QUADS'

    def draw_buttons_ext(self, context, layout):
         """ Draw in sidebar """
         self.draw_buttons(context, layout) # Используем тот же UI


    # --- Очистка ---
    def clear_object(self):
        """Removes the associated Blender object and mesh."""
        obj_name = self.target_object_name
        if obj_name and obj_name in bpy.data.objects:
            obj = bpy.data.objects[obj_name]
            mesh = obj.data
            logger.debug(f"Clearing object: Removing Blender object '{obj_name}' and mesh '{mesh.name if mesh else 'None'}'")
            try:
                bpy.data.objects.remove(obj, do_unlink=True)
                if mesh and mesh.users == 0:
                    # logger.debug(f"Removing unused mesh '{mesh.name}' during clear.")
                    bpy.data.meshes.remove(mesh, do_unlink=True)
            except Exception as e:
                logger.error(f"Error during object/mesh removal in clear_object for '{obj_name}': {e}")
        if self.target_object_name:
            self.target_object_name = ""


    def sv_free(self):
        """Called when the node is removed."""
        self.clear_object()

    # --- Обработка ---
    def process(self):
        # logger.debug(f"--- CQViewerNode process START for node {self.name} ---")
        # --- Получаем сокеты безопасно ---
        
        input_socket = self.inputs["Object In"]
        socket_tol = self.inputs["Tolerance"]
        socket_ang =  self.inputs["Angular Tol."]

        if not input_socket: logger.warning(f"Node {self.name}: Input socket not found."); return
        if not socket_tol: logger.warning(f"Node {self.name}: Tolerance socket not found."); return
        if not socket_ang: logger.warning(f"Node {self.name}: Angular Tol. socket not found."); return

        # --- Проверка подключения основного входа ---
        if not input_socket.is_linked:
            self.clear_object()
            # logger.debug(f"Node {self.name}: Input not linked. Clearing object.")
            return

        # --- Получение входных данных ---
        cq_input = None
        target_obj = None # Инициализируем
        old_mesh_to_remove = None # Инициализируем
        try:
            cq_input = input_socket.sv_get()
            # --- Получаем точность ---
            if socket_tol.is_linked: tolerance = socket_tol.sv_get()
            else: tolerance = self.tessellation_tolerance_
            if socket_ang.is_linked: angular = socket_ang.sv_get()
            else: angular = self.tessellation_angular_
            
            logger.warning(f"Node {self.tessellation_tolerance_}: Angular Tol. socket not found.")
            logger.warning(f"Node {self.tessellation_angular_}: Angular Tol. socket not found.")

            # Убедимся, что значения положительные
            if not isinstance(tolerance, (int, float)) or tolerance <= 0: tolerance = 0.001
            if not isinstance(angular, (int, float)) or angular <= 0: angular = 0.01
           

            if cq_input is None:
                self.clear_object()
                return # Не ошибка, просто нечего отображать

            shape_to_convert = None
            if isinstance(cq_input, cq.Workplane):
                all_shapes_on_stack = cq_input.vals() # Получаем ВСЕ Shape на стеке
                if all_shapes_on_stack:
                    if len(all_shapes_on_stack) > 1:
                        logger.debug(f"Viewer: Input Workplane has {len(all_shapes_on_stack)} shapes. Attempting to combine them.")
                        # --- Пытаемся объединить все shape в один ---
                        # Вариант 1: Используем cq.Workplane().add(list_of_shapes), он должен их объединить
                        temp_wp_for_combine = cq.Workplane("XY")
                        for s in all_shapes_on_stack:
                             if isinstance(s, cq.Shape) and s.isValid():
                                 temp_wp_for_combine = temp_wp_for_combine.add(s)
                             # else: logger.warning("Skipping invalid shape during combine.")

                        combined_vals = temp_wp_for_combine.vals()
                        if combined_vals and isinstance(combined_vals[0], cq.Shape):
                             shape_to_convert = combined_vals[0]
                             logger.debug(f"  Shapes combined into one. Resulting shape type: {type(shape_to_convert)}")
                        else:
                             logger.warning("Failed to combine multiple shapes from Workplane into one. Using first shape.")
                             shape_to_convert = all_shapes_on_stack[0] # Запасной вариант - берем первый
                        # --------------------------------------------
                    elif isinstance(all_shapes_on_stack[0], cq.Shape):
                        shape_to_convert = all_shapes_on_stack[0] # Один Shape на стеке
                    else:
                        raise ViewerError(self, "Input Workplane does not contain a valid Shape on stack.")
                else:
                    raise ViewerError(self, "Input Workplane is empty (no shapes on stack).")
            elif isinstance(cq_input, cq.Shape):
                shape_to_convert = cq_input
            else:
                raise NodeProcessingError(self, f"Unsupported input type: {type(cq_input)}")

            if not shape_to_convert or not shape_to_convert.isValid():
                 self.clear_object(); raise ViewerError(self, "Final shape to convert is invalid or empty.")

        except Exception as e:
            self.clear_object() # Очищаем объект при ошибке на входе
            if isinstance(e, (NodeProcessingError, SocketConnectionError, ViewerError)): raise
            else: raise NodeProcessingError(self, f"Input error: {e}")


        # --- Конвертация в Blender Mesh с учетом точности ---
        mesh_name = f"CQ_{self.id_data.name}_{self.name}_Mesh"
        new_blender_mesh = None
        try:
            new_blender_mesh = cq_utils.shape_to_blender_mesh(
                shape_to_convert, mesh_name,
                tolerance=tolerance, angular_tolerance=angular
            )
            if new_blender_mesh is None:
                raise ViewerError(self, "Mesh conversion returned None.")
        except Exception as e:
            self.clear_object()
            raise ViewerError(self, f"Mesh conversion failed: {e}")

        # --- Обновление/Создание объекта Blender ---
        try:
            if self.target_object_name and self.target_object_name in bpy.data.objects:
                target_obj = bpy.data.objects[self.target_object_name]
                old_mesh_to_remove = target_obj.data
                # logger.debug(f"Updating existing object '{target_obj.name}' with new mesh '{new_blender_mesh.name}'")
                target_obj.data = new_blender_mesh
            else:
                if not self.target_object_name or self.target_object_name in bpy.data.objects: # Генерируем новое имя
                     base_name = f"CQ_{self.id_data.name}_{self.name}"; current_target_name = base_name; count = 1
                     while current_target_name in bpy.data.objects: current_target_name = f"{base_name}.{count:03d}"; count += 1
                     self.target_object_name = current_target_name

                # logger.debug(f"Creating new Blender object: {self.target_object_name}")
                target_obj = bpy.data.objects.new(self.target_object_name, new_blender_mesh)
                bpy.context.collection.objects.link(target_obj)

        except Exception as e:
             logger.error(f"Failed to update/create Blender object '{self.target_object_name}': {e}", exc_info=True)
             # Если не удалось создать/обновить объект, удаляем новый меш, чтобы не было утечек
             if new_blender_mesh and new_blender_mesh.users == 0: bpy.data.meshes.remove(new_blender_mesh)
             self.clear_object() # Пытаемся очистить старый объект, если он был
             raise ViewerError(self, f"Failed to update/create Blender object: {e}")

        # --- Очистка старого меша ---
        if old_mesh_to_remove and old_mesh_to_remove != new_blender_mesh and old_mesh_to_remove.users == 0:
            # logger.debug(f"Removing unused old mesh: '{old_mesh_to_remove.name}'")
            try: bpy.data.meshes.remove(old_mesh_to_remove, do_unlink=True)
            except: logger.warning(f"Old mesh '{old_mesh_to_remove.name}' failed to remove.")

        # --- Обновление отображения ---
        if target_obj: target_obj.update_tag(refresh={'DATA'})
        # logger.debug(f"--- CQViewerNode process END for node {self.name} ---")


# --- Регистрация ---
classes = (
    CQViewerNode, # Используем новое имя класса
)