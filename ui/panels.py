# cadquery_parametric_addon/ui/panels.py
import bpy
from ..core.node_tree import CadQueryNodeTree

class CQP_PT_NodeEditorPanel(bpy.types.Panel):
    """Creates a Panel in the Node Editor Sidebar"""
    bl_label = "CadQuery I/O"
    bl_idname = "CQP_PT_NodeEditorPanel"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "CadQuery" # Имя вкладки

    @classmethod
    def poll(cls, context):
        # Показываем панель всегда в редакторе нод,
        # но кнопки могут быть неактивны, если дерево не то.
        return context.space_data and context.space_data.type == 'NODE_EDITOR'

    def draw_header(self, context):
        # Добавляем иконку в заголовок панели
        layout = self.layout
        layout.label(text="", icon='FILE_SCRIPT')

    def draw(self, context):
        """Рисует содержимое панели."""
        layout = self.layout
        node_tree = context.space_data.node_tree
        is_cqp_tree = isinstance(node_tree, CadQueryNodeTree)

        box = layout.box()
        if is_cqp_tree:
            box.label(text=f"Active Tree: {node_tree.name}", icon='NODETREE')
        else:
            # Делаем текст ошибки более заметным
            sub_box = box.box() # Вложенный бокс для выделения
            sub_box.alert = True
            sub_box.label(text="Active tree is not CadQuery type!", icon='ERROR')

        # Используем отдельную строку для кнопок
        row = box.row(align=True)

        # --- Управляем активностью строки для кнопки Экспорта ---
        row_export = row.row(align=True) # Вложенная строка для управления enabled
        row_export.enabled = is_cqp_tree # Строка активна, только если дерево наше
        row_export.operator("cqp.export_json_v2", text="Export", icon='EXPORT')
        # -------------------------------------------------------

        # Кнопка Импорта (активна всегда, оператор сам проверит дерево)
        row.operator("cqp.import_json_v2", text="Import Add", icon='IMPORT')

# --- Регистрация ---
classes = (
    CQP_PT_NodeEditorPanel,
)

def register():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)

def unregister():
    from bpy.utils import unregister_class
    for cls in reversed(classes):
        try: unregister_class(cls)
        except RuntimeError: print(f"Warning: Could not unregister panel class {cls.__name__}")