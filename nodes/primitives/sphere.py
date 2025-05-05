# cadquery_parametric_addon/nodes/primitives/sphere.py
import bpy
from bpy.props import FloatProperty

from ...core.node_tree import CadQueryNode
from ...core.sockets import CQObjectSocket, CQNumberSocket
from ...core.cad_manager import cad_manager
from ...core.exceptions import NodeProcessingError

class SphereNode(CadQueryNode):
    """Creates a CadQuery Sphere primitive."""
    bl_idname = 'CQPNode_PrimitiveSphereNode'
    bl_label = 'Sphere'
    sv_category = 'Primitives'

    # --- Свойства Ноды ---
    radius_: FloatProperty(
        name="Radius", default=0.5, min=0.001,
        description="Sphere radius",
        update=CadQueryNode.process_node
    )

    # --- Инициализация ---
    def sv_init(self, context):
        """Initialize sockets."""
        self.inputs.new(CQNumberSocket.bl_idname, "Radius").prop_name = 'radius_'
        self.outputs.new(CQObjectSocket.bl_idname, "Sphere Object")

    # --- UI ---
    def draw_buttons(self, context, layout):
        """Draw UI."""
        super().draw_buttons(context, layout) # Ошибки
        # Поле ввода будет нарисовано сокетом

    # --- Обработка ---
    def process(self):
        """Node's core logic."""
        try:
            radius = self.inputs["Radius"].sv_get() if self.inputs["Radius"].is_linked else self.radius_

            if radius <= 0: raise NodeProcessingError(self, "Radius must be positive.")

        except NodeProcessingError: raise
        except Exception as e:
            raise NodeProcessingError(self, f"Input error: {e}")

        # Выполняем операцию CadQuery
        try:
            # Используем cad_manager. Workplane.sphere(radius)
            result_wp = cad_manager.execute_primitive("sphere", radius)
            self.outputs["Sphere Object"].sv_set(result_wp)
        except Exception as e:
            raise NodeProcessingError(self, f"CadQuery sphere failed: {e}")


# --- Регистрация ---
classes = (
    SphereNode,
)