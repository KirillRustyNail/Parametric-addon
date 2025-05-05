# cadquery_parametric_addon/operators/node_ops.py
import bpy
from ..core.node_tree import CadQueryNodeTree # Нужен ID дерева

class CQP_OT_AddNodeTree(bpy.types.Operator):
    """Adds a new CadQuery Node Tree"""
    bl_idname = "cqp.add_node_tree"
    bl_label = "Add CadQuery Node Tree"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # Создаем новое дерево нод
        node_tree = bpy.data.node_groups.new(name="CadQuery Tree", type=CadQueryNodeTree.bl_idname)
        if not node_tree:
            self.report({'ERROR'}, "Failed to create CadQuery Node Tree.")
            return {'CANCELLED'}

        # Если активный объект - редактор нод, используем это дерево
        if context.space_data and context.space_data.type == 'NODE_EDITOR':
            context.space_data.node_tree = node_tree
        else:
            # Иначе просто сообщаем об успехе
            self.report({'INFO'}, f"Created Node Tree: {node_tree.name}")

        return {'FINISHED'}

# Можно добавить операторы для других действий с нодами/деревом, если нужно

# --- Registration ---
classes = (
    CQP_OT_AddNodeTree,
)

def register():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)

def unregister():
    from bpy.utils import unregister_class
    for cls in reversed(classes):
        try:
            unregister_class(cls)
        except RuntimeError:
             logger.error(f"Failed to unregister operator class: {cls.__name__}")