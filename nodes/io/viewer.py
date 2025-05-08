# cadquery_parametric_addon/nodes/io/viewer.py
# (Или nodes/io/cq_viewer.py, если вы переименовали)

import bpy
from bpy.props import StringProperty, FloatProperty, BoolProperty
import logging
import math

from ...core.node_tree import CadQueryNode
from ...core.sockets import CQObjectSocket, CQNumberSocket
from ...utils import cq_utils
from ...core.exceptions import NodeProcessingError, ViewerError, SocketConnectionError
from ...dependencies import cq


logger = logging.getLogger(__name__)
# Импорт оператора (если он в отдельном файле)
try:
    # Пытаемся импортировать, если он в отдельном файле
    from ...operators.process_mesh import CQP_OT_ProcessMeshOp
except ImportError:
    logger.warning("CQP_OT_ProcessMeshOp not found in operators.process_mesh. Buttons might not work.")
    # Определяем заглушку, чтобы код не падал
    class CQP_OT_ProcessMeshOp: pass



# --- Нода ---
class CQViewerNode(CadQueryNode):
    """Displays the result of a CadQuery operation in the Blender scene
       and provides mesh processing options."""
    bl_idname = 'CQPNode_IOCQViewerNode'
    bl_label = 'CQ Viewer'
    sv_category = 'Input/Output'

    # --- Свойства ---
    target_object_name: StringProperty( default="" )
    tessellation_tolerance_: FloatProperty( name="Tolerance", default=0.1, min=0.001, max=1.0, precision=3, subtype='FACTOR', update=CadQueryNode.process_node )
    tessellation_angular_: FloatProperty( name="Angular Tol.", default=0.1, min=0.01, max=1.0, precision=2, subtype='FACTOR', update=CadQueryNode.process_node )

    # --- Инициализация ---
    def sv_init(self, context):
        self.inputs.new(CQObjectSocket.bl_idname, "Object In")
        socket_tol = self.inputs.new(CQNumberSocket.bl_idname, "Tolerance"); socket_tol.prop_name = 'tessellation_tolerance_'
        socket_ang = self.inputs.new(CQNumberSocket.bl_idname, "Angular Tol."); socket_ang.prop_name = 'tessellation_angular_'
        try: # Синхронизация UI сокетов
            socket_tol.default_property = self.tessellation_tolerance_
            socket_ang.default_property = self.tessellation_angular_
        except Exception as e: logger.error(f"Error syncing tolerance sockets in {self.name}: {e}")

    # --- UI ---
    def draw_buttons(self, context, layout):
        super().draw_buttons(context, layout)
        layout.prop(self, "target_object_name", text="Output Name")

        box_tess = layout.box()
        box_tess.label(text="Tessellation:")
        row_tess = box_tess.row(align=True)
        row_tess.prop(self, "tessellation_tolerance_", text="Tol", slider=True)
        row_tess.prop(self, "tessellation_angular_", text="Ang", slider=True)

        layout.separator()
        col_ops = layout.column(align=True)
        col_ops.label(text="Mesh Ops:")
        
        can_process = bool(self.target_object_name and self.target_object_name in bpy.data.objects)

        row_merge = col_ops.row(align=True)
        row_merge.enabled = can_process
        op_merge = row_merge.operator("cqp.process_mesh_op", text="Merge by Distance", icon='AUTOMERGE_ON')
        op_merge.node_path = self.get_path()
        op_merge.operation = 'MERGE'
        row_quads = col_ops.row(align=True)
        row_quads.enabled = can_process
        op_quads = row_quads.operator("cqp.process_mesh_op", text="Tris to Quads", icon='MOD_TRIANGULATE')
        op_quads.node_path = self.get_path(); op_quads.operation = 'QUADS'

    def draw_buttons_ext(self, context, layout): self.draw_buttons(context, layout)

    # --- Очистка ---
    def clear_object(self):
        obj_name = self.target_object_name
        if obj_name and obj_name in bpy.data.objects:
            obj = bpy.data.objects[obj_name]; mesh = obj.data
            logger.debug(f"Clearing object: Removing '{obj_name}'")
            try:
                bpy.data.objects.remove(obj, do_unlink=True)
                if mesh and mesh.users == 0: bpy.data.meshes.remove(mesh, do_unlink=True)
            except Exception as e: logger.error(f"Error removing '{obj_name}': {e}")
        if self.target_object_name: self.target_object_name = ""

    def sv_free(self): self.clear_object()

    # --- Обработка (без объединения здесь) ---
    def process(self):
        # logger.debug(f"--- CQViewerNode process START for node {self.name} ---")
        input_socket = self.inputs.get("Object In")
        socket_tol = self.inputs.get("Tolerance"); socket_ang = self.inputs.get("Angular Tol.")
        if not input_socket or not socket_tol or not socket_ang: return # Сокеты не готовы

        if not input_socket.is_linked: self.clear_object(); return

        cq_input = None; target_obj = None; old_mesh_to_remove = None
        try:
            cq_input = input_socket.sv_get()
            tolerance = socket_tol.sv_get() if socket_tol.is_linked else self.tessellation_tolerance_
            angular = socket_ang.sv_get() if socket_ang.is_linked else self.tessellation_angular_
            if tolerance <= 0: tolerance = 0.001
            if angular <= 0: angular = 0.01

            if cq_input is None: self.clear_object(); return

            # --- Получение Shape из cq_input (ожидаем один Shape) ---
            shape_to_convert = None
            if isinstance(cq_input, cq.Workplane):
                vals = cq_input.vals()
                if vals and isinstance(vals[0], cq.Shape):
                    shape_to_convert = vals[0]
                    if len(vals) > 1: logger.warning(f"Viewer '{self.name}': Input WP has multiple shapes ({len(vals)}). Using first.")
                else: raise ViewerError(self, "Input Workplane empty or invalid.")
            elif isinstance(cq_input, cq.Shape):
                shape_to_convert = cq_input
            else: raise NodeProcessingError(self, f"Unsupported input type: {type(cq_input)}")

            if not shape_to_convert or not shape_to_convert.isValid():
                 self.clear_object(); raise ViewerError(self, "Final shape to convert is invalid.")
            # ---------------------------------------------------

            # --- Конвертация ---
            mesh_name = f"CQ_{self.id_data.name}_{self.name}_Mesh"
            new_blender_mesh = cq_utils.shape_to_blender_mesh(shape_to_convert, mesh_name, tolerance=tolerance, angular_tolerance=angular)
            if new_blender_mesh is None: raise ViewerError(self, "Mesh conversion returned None.")

            # --- Обновление/Создание объекта Blender ---
            if self.target_object_name and self.target_object_name in bpy.data.objects:
                target_obj = bpy.data.objects[self.target_object_name]
                old_mesh_to_remove = target_obj.data
                target_obj.data = new_blender_mesh
            else:
                # ... (генерация уникального имени target_object_name) ...
                if not self.target_object_name or self.target_object_name in bpy.data.objects:
                     base_name = f"CQ_{self.id_data.name}_{self.name}"; cn = base_name; count = 1
                     while cn in bpy.data.objects: cn = f"{base_name}.{count:03d}"; count += 1
                     self.target_object_name = cn
                target_obj = bpy.data.objects.new(self.target_object_name, new_blender_mesh)
                bpy.context.collection.objects.link(target_obj)

            # --- Очистка старого меша ---
            if old_mesh_to_remove and old_mesh_to_remove != new_blender_mesh and old_mesh_to_remove.users == 0:
                try: bpy.data.meshes.remove(old_mesh_to_remove, do_unlink=True)
                except: logger.warning(f"Old mesh '{old_mesh_to_remove.name}' failed to remove?")

            if target_obj: target_obj.update_tag(refresh={'DATA'})

        except Exception as e:
            self.clear_object() # Очищаем объект при любой ошибке в process
            if isinstance(e, (NodeProcessingError, SocketConnectionError, ViewerError)): raise
            else:
                logger.error(f"Unexpected error in CQViewerNode process: {e}", exc_info=True)
                raise NodeProcessingError(self, f"Viewer processing failed: {e}")
        # logger.debug(f"--- CQViewerNode process END for node {self.name} ---")

# --- Регистрация ---
classes = (
    CQViewerNode,
)