# cadquery_parametric_addon/core/node_tree.py
import bpy
from bpy.props import StringProperty, BoolProperty
from bpy.types import NodeTree, Node
import time
import traceback
import logging # Добавляем логгер

from .constants import UPDATE_KEY, ERROR_KEY, ERROR_STACK_KEY
from .event_system import handle_event, TreeEvent, PropertyEvent
from .exceptions import DependencyError
from ..dependencies import check_dependencies, cadquery_available

logger = logging.getLogger(__name__) # Создаем логгер

# --- Base Node Tree Class ---
class CadQueryNodeTree(NodeTree):
    """Custom Node Tree for CadQuery Parametric Modeling."""
    bl_idname = 'CadQueryNodeTreeType'
    bl_label = 'CadQuery Nodes'
    bl_icon = 'NODETREE'

    sv_process: BoolProperty(
        name="Process Live", default=True,
        description="Automatically update the tree when nodes or properties change",
        update=lambda s, c: handle_event(TreeEvent(s))
    )

    tree_id_memory: StringProperty(options={'SKIP_SAVE'}, default="") # Переименовано и добавлен default

    @property
    def tree_id(self):
        if not self.tree_id_memory:
            self.tree_id_memory = str(hash(self) ^ hash(time.monotonic()))
        return self.tree_id_memory

    def update(self):
        if bpy.context: # Простая проверка на существование контекста
             handle_event(TreeEvent(self))

    def update_nodes(self, nodes_to_update):
        if self.sv_process:
            handle_event(PropertyEvent(self, nodes_to_update))

    def update_ui(self, nodes_errors):
         for node, error_info in zip(self.nodes, nodes_errors):
             if hasattr(node, 'update_node_ui'):
                 node.update_node_ui(error_info.get('error'), error_info.get('stack'))


# --- Base Node Class ---
class CadQueryNode(Node):
    """Base class for all CadQuery nodes."""
    bl_idname_prefix = "CQPNode_"

    n_id: StringProperty(options={'SKIP_SAVE'})

    @property
    def node_id(self):
        if not self.n_id:
            self.n_id = str(hash(self) ^ hash(time.monotonic()))
        return self.n_id

    def set_error(self, error_message: str | None, stack_trace: str | None = None):
        if error_message:
            self[ERROR_KEY] = error_message
            self[ERROR_STACK_KEY] = stack_trace if stack_trace else "".join(traceback.format_exc())
            self[UPDATE_KEY] = False
        else:
            if ERROR_KEY in self: del self[ERROR_KEY]
            if ERROR_STACK_KEY in self: del self[ERROR_STACK_KEY]
            self[UPDATE_KEY] = True

    def get_error(self) -> str | None:
        return self.get(ERROR_KEY)

    def is_updated(self) -> bool:
        return self.get(UPDATE_KEY, False)

    def sv_init(self, context): pass
    def process(self): raise NotImplementedError("Subclasses must implement the process method.")
    def sv_update(self): pass
    def sv_free(self): pass
    def sv_copy(self, original):
        self.n_id = ""
        for sock in self.inputs: sock.s_id = ""
        for sock in self.outputs: sock.s_id = ""

    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == CadQueryNodeTree.bl_idname

    def init(self, context):
        """Blender's initialization method."""
        try:
            if not cadquery_available:
                 dep_error = DependencyError("CadQuery library not found or failed to import.")
                 self.set_error(str(dep_error))
            else:
                self.sv_init(context)
        except Exception as e:
             # Ловим ошибки из sv_init тоже
             self.set_error(f"Initialization error: {e}", "".join(traceback.format_exc()))
             logger.error(f"Error during sv_init for node {self.name}: {e}", exc_info=True)


    def free(self):
        """Blender's removal method."""
        # Очищаем кеш сокетов
        # Импортируем здесь, чтобы избежать раннего импорта
        from .data_cache import sv_forget_socket
        for s in self.inputs: sv_forget_socket(s.socket_id)
        for s in self.outputs: sv_forget_socket(s.socket_id)
        # Вызываем наш метод очистки
        try:
            self.sv_free()
        except Exception as e:
            logger.error(f"Error during sv_free for node {self.name}: {e}", exc_info=True)
        # Обновляем UI (убираем ошибку, если была)
        self.update_node_ui(None)


    def copy(self, original):
        """Blender's copy method."""
        try:
            self.sv_copy(original) # Должен сбросить n_id и s_id сокетов
        except Exception as e:
            logger.error(f"Error during sv_copy for node {self.name}: {e}", exc_info=True)

    def update(self):
        """Blender's update method for structural changes."""
        try:
            self.sv_update()
        except Exception as e:
             self.set_error(f"Link update error: {e}", "".join(traceback.format_exc()))
             logger.error(f"Error during sv_update for node {self.name}: {e}", exc_info=True)
        # Не сигнализируем здесь, это делает NodeTree.update()

    # --- Метод process_node с проверкой флага ---
    def process_node(self, context=None):
        """Signals that this node needs to be reprocessed, unless importing."""
        # --- Проверка флага импорта ---
        if self.id_data.get("_is_importing", False):
            # logger.debug(f"Skipping process_node for {self.name} during import.")
            return # Не запускаем обновление во время импорта
        # -------------------------------

        # logger.debug(f"--- PROCESS_NODE called for: {self.name} ({self.bl_idname}) ---")
        if hasattr(self.id_data, 'update_nodes'):
            self.id_data.update_nodes([self])
            # logger.debug(f"  Called id_data.update_nodes for {self.name}")
        # else:
            # logger.warning(f"  Node {self.name} has no id_data with update_nodes method.")


    def draw_buttons(self, context, layout):
        """Draw node properties in the node UI (standard panel)."""
        err = self.get_error()
        if err:
            box = layout.box(); box.alert = True
            lines = err.split(': ', 1)
            box.label(text=lines[0] + ":" if len(lines) > 1 else err, icon='ERROR')
            if len(lines) > 1:
                 for line in lines[1].split('\n'): box.label(text=line)
            if self.get(ERROR_STACK_KEY):
                 op = box.operator("cqp.show_error_details", text="Details", icon='CONSOLE')
                 op.node_path = self.get_path()

    def draw_buttons_ext(self, context, layout):
        """Draw node properties in the sidebar (N-panel)."""
        self.draw_buttons(context, layout)

    def update_node_ui(self, error_message=None, stack_trace=None):
        """Updates the visual state of the node (e.g., color based on error)."""
        if error_message:
            self.use_custom_color = True
            self.color = (0.7, 0.1, 0.1)
        else:
            self.use_custom_color = False
        # Убрали self.update_tag()

    def get_path(self):
        """Возвращает путь к ноде вида 'TreeName/NodeName'."""
        return f"{self.id_data.name}/{self.name}"


# --- Оператор для показа деталей ошибки (с исправленным popup_menu) ---
class CQP_OT_ShowErrorDetails(bpy.types.Operator):
    bl_idname = "cqp.show_error_details"
    bl_label = "CadQuery Node Error Details"
    bl_options = {'REGISTER', 'INTERNAL'}

    node_path: StringProperty()

    def draw(self, context):
        layout = self.layout
        try:
            tree_name, node_name = self.node_path.split('/')
            node = bpy.data.node_groups[tree_name].nodes[node_name]
            error_message = node.get(ERROR_KEY, "No error message.")
            stack_trace = node.get(ERROR_STACK_KEY, "No stack trace available.")
        except Exception as e:
            layout.label(text=f"Error retrieving details: {e}", icon='ERROR')
            return

        layout.label(text="Error:")
        box = layout.box(); box.scale_y=0.8 # Уменьшаем бокс
        for line in error_message.split('\n'): box.label(text=line)

        layout.separator()
        layout.label(text="Stack Trace:")
        box = layout.box(); box.scale_y=0.8
        lines = stack_trace.strip().split('\n')
        max_lines = 20
        for i, line in enumerate(lines):
            if i >= max_lines: box.label(text="..."); break
            box.label(text=line.replace(' ', '\u00A0')) # Неразрывные пробелы

    def execute(self, context):
        if not self.node_path:
            self.report({'ERROR'}, "Node path not provided for error details.")
            return {'CANCELLED'}
        try:
            tree_name, node_name = self.node_path.split('/')
            if tree_name not in bpy.data.node_groups or node_name not in bpy.data.node_groups[tree_name].nodes:
                 raise LookupError(f"Node '{self.node_path}' not found.")
            context.window_manager.popup_menu(
                self.draw, # <--- Передаем метод экземпляра
                title="Error Details",
                icon='ERROR'
            )
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Could not find node or show details: {e}")
            return {'CANCELLED'}


# --- Регистрация ---
classes = (
    CadQueryNodeTree,
    CQP_OT_ShowErrorDetails,
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
             logger.warning(f"Could not unregister node tree class: {cls.__name__}")