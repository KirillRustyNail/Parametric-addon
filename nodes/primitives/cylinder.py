# cadquery_parametric_addon/nodes/primitives/cylinder.py
import bpy
from bpy.props import FloatProperty, BoolProperty

from ...core.node_tree import CadQueryNode
from ...core.sockets import CQObjectSocket, CQNumberSocket, CQBooleanSocket
from ...core.cad_manager import cad_manager
from ...core.exceptions import NodeProcessingError

class CylinderNode(CadQueryNode):
    """Creates a CadQuery Cylinder primitive."""
    bl_idname = 'CQPNode_PrimitiveCylinderNode'
    bl_label = 'Cylinder'
    sv_category = 'Primitives'

    # --- Свойства Ноды ---
    height_: FloatProperty(
        name="Height", default=1.0, min=0.001,
        description="Cylinder height (along Z axis)",
        update=CadQueryNode.process_node
    )
    radius_: FloatProperty(
        name="Radius", default=0.5, min=0.001,
        description="Cylinder radius",
        update=CadQueryNode.process_node
    )

    # --- Инициализация ---
    def sv_init(self, context):
        """Initialize sockets."""
        self.inputs.new(CQNumberSocket.bl_idname, "Height").prop_name = 'height_'
        self.inputs.new(CQNumberSocket.bl_idname, "Radius").prop_name = 'radius_'
        self.outputs.new(CQObjectSocket.bl_idname, "Cylinder Object")

    # --- UI ---
    def draw_buttons(self, context, layout):
        """Draw UI."""
        super().draw_buttons(context, layout) # Ошибки
        # Поля ввода будут нарисованы сокетами

    # --- Обработка ---
    def process(self):
        """Node's core logic."""
        try:
            height = self.inputs["Height"].sv_get() if self.inputs["Height"].is_linked else self.height_
            radius = self.inputs["Radius"].sv_get() if self.inputs["Radius"].is_linked else self.radius_

            if height <= 0: raise NodeProcessingError(self, "Height must be positive.")
            if radius <= 0: raise NodeProcessingError(self, "Radius must be positive.")

        except NodeProcessingError: raise
        except Exception as e:
            raise NodeProcessingError(self, f"Input error: {e}")

        # Выполняем операцию CadQuery
        try:
            # Используем cad_manager. Workplane.cylinder(height, radius)
            # Он создает цилиндр вдоль оси Z, центрированный по XY.
            result_wp = cad_manager.execute_primitive("cylinder", height, radius)
            self.outputs["Cylinder Object"].sv_set(result_wp)
        except Exception as e:
            raise NodeProcessingError(self, f"CadQuery cylinder failed: {e}")


# --- Регистрация ---
classes = (
    CylinderNode,
)