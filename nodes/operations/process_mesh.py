# cadquery_parametric_addon/operators/process_mesh.py
import bpy
from bpy.props import StringProperty, EnumProperty, FloatProperty
import logging
import math

logger = logging.getLogger(__name__)

class CQP_OT_ProcessMeshOp(bpy.types.Operator):
    """Applies mesh processing operations to the CQ Viewer output object."""
    bl_idname = "cqp.process_mesh_op"
    bl_label = "Process Viewer Mesh"
    bl_options = {'REGISTER', 'UNDO'}

    node_path: StringProperty(name="Node Path", description="Path to the CQ Viewer node")
    operation: EnumProperty(
        name="Operation",
        items=[('MERGE', "Merge by Distance", "Merge vertices by distance"),
               ('QUADS', "Tris to Quads", "Convert triangles to quads")],
        default='MERGE'
    )
    # Опции для операций (можно добавить как свойства оператора)
    merge_distance: FloatProperty(name="Merge Distance", default=0.001, min=0.0, subtype='DISTANCE')
    quad_face_angle: FloatProperty(name="Max Face Angle", default=45.0, min=0.0, max=180.0, subtype='ANGLE')
    quad_shape_angle: FloatProperty(name="Max Shape Angle", default=45.0, min=0.0, max=180.0, subtype='ANGLE')

    @classmethod
    def poll(cls, context):
        # Проверяем, что мы в объектном режиме (операторы редактирования требуют этого)
        return context.mode == 'OBJECT'

    def invoke(self, context, event):
        # Показываем всплывающее окно для настройки параметров операции
        if self.operation == 'MERGE':
             return context.window_manager.invoke_props_dialog(self, width=200)
        elif self.operation == 'QUADS':
             return context.window_manager.invoke_props_dialog(self, width=250)
        return self.execute(context) # Для других операций (если будут) без параметров

    def draw(self, context):
        # Рисуем параметры во всплывающем окне
        layout = self.layout
        if self.operation == 'MERGE':
             layout.prop(self, "merge_distance")
        elif self.operation == 'QUADS':
             layout.prop(self, "quad_face_angle")
             layout.prop(self, "quad_shape_angle")


    def execute(self, context):
        if not self.node_path:
            self.report({'ERROR'}, "Target node path not set."); return {'CANCELLED'}

        # --- Находим ноду и объект ---
        try:
            tree_name, node_name = self.node_path.split('/')
            node = bpy.data.node_groups[tree_name].nodes[node_name]
            # Получаем имя объекта из ноды
            obj_name = node.target_object_name
            if not obj_name or obj_name not in bpy.data.objects:
                raise LookupError(f"Viewer node '{node_name}' has no valid target object '{obj_name}'.")
            obj = bpy.data.objects[obj_name]
            if obj.type != 'MESH':
                 raise TypeError(f"Target object '{obj_name}' is not a Mesh.")
        except (ValueError, KeyError, LookupError, TypeError, AttributeError) as e:
            self.report({'ERROR'}, f"Cannot find target node or object: {e}"); return {'CANCELLED'}

        # --- Выполняем операцию ---
        logger.info(f"Applying '{self.operation}' to object '{obj.name}'...")
        # Запоминаем активный объект и режим
        current_active = context.view_layer.objects.active
        current_mode = context.object.mode if context.object else 'OBJECT'
        selected_objects = context.selected_objects[:]

        try:
            # Переключаемся в объектный режим и делаем объект активным/выделенным
            if current_mode != 'OBJECT': bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.select_all(action='DESELECT')
            context.view_layer.objects.active = obj
            obj.select_set(True)

            # Вызов оператора редактирования
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT') # Выделяем все в меше

            if self.operation == 'MERGE':
                bpy.ops.mesh.remove_doubles(threshold=self.merge_distance)
                self.report({'INFO'}, f"Applied Merge by Distance (Threshold: {self.merge_distance:.4f})")
            elif self.operation == 'QUADS':
                # bpy.ops.mesh.tris_convert_to_quads() # Старый оператор
                bpy.ops.mesh.beautify_fill(angle_limit=math.radians(self.quad_shape_angle)) # Попробуем этот
                self.report({'INFO'}, f"Applied Tris to Quads (Beautify Fill)")

            bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.object.mode_set(mode='OBJECT') # Возвращаемся в объектный режим

        except Exception as e:
            logger.error(f"Operation '{self.operation}' failed: {e}", exc_info=True)
            self.report({'ERROR'}, f"Operation '{self.operation}' failed: {e}")
            # Пытаемся вернуться в исходный режим
            try: bpy.ops.object.mode_set(mode=current_mode)
            except: pass
            return {'CANCELLED'}
        finally:
            # Восстанавливаем выделение и активный объект
            bpy.ops.object.select_all(action='DESELECT')
            for sel_obj in selected_objects:
                 if sel_obj and sel_obj.name in context.view_layer.objects: # Проверяем существование
                      sel_obj.select_set(True)
            if current_active and current_active.name in context.view_layer.objects:
                 context.view_layer.objects.active = current_active
            # Возвращаемся в исходный режим, если не вернулись в try
            if context.object and context.object.mode != current_mode:
                 try: bpy.ops.object.mode_set(mode=current_mode)
                 except: pass


        return {'FINISHED'}


# --- Регистрация ---
classes = (
    CQP_OT_ProcessMeshOp,
)

def register():
    from bpy.utils import register_class
    for cls in classes: register_class(cls)

def unregister():
    from bpy.utils import unregister_class
    for cls in reversed(classes):
        try: unregister_class(cls)
        except RuntimeError: print(f"Warning: Could not unregister operator class {cls.__name__}")