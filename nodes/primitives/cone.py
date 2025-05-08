# cadquery_parametric_addon/nodes/primitives/cone.py
import bpy
from bpy.props import FloatProperty, BoolProperty

import logging

from ...core.node_tree import CadQueryNode
from ...core.sockets import CQObjectSocket, CQNumberSocket, CQBooleanSocket
from ...core.cad_manager import cad_manager
from ...core.exceptions import NodeProcessingError
from ...dependencies import cq 

logger = logging.getLogger(__name__)

class ConeNode(CadQueryNode):
    """Creates a CadQuery Cone primitive."""
    bl_idname = 'CQPNode_PrimitiveConeNode'
    bl_label = 'Cone'
    sv_category = 'Primitives'

    # --- Свойства Ноды ---
    height_: FloatProperty(
        name="Height", default=1.0, min=0.001,
        description="Cone height (along Z axis)",
        update=CadQueryNode.process_node
    )
    bottom_radius_: FloatProperty(
        name="Bottom Radius", default=0.5, min=0.0, # Может быть 0 для острого конца
        description="Radius of the cone base",
        update=CadQueryNode.process_node
    )
    top_radius_: FloatProperty(
        name="Top Radius", default=0.0001, min=0.0, # Может быть 0 для острого конца
        description="Radius of the cone top (0 for a standard cone)",
        update=CadQueryNode.process_node
    )
    centered_: BoolProperty(
        name="Centered", default=True,
        description="Create the cone centered at the origin (height-wise)",
        update=CadQueryNode.process_node
    )

    # --- Инициализация ---
    def sv_init(self, context):
        """Initialize sockets."""
        logger.debug(f"--- ConeNode sv_init START for node {self.name} ---")
        try:
            socket_h = self.inputs.new(CQNumberSocket.bl_idname, "Height"); socket_h.prop_name = 'height_'
            socket_br = self.inputs.new(CQNumberSocket.bl_idname, "Bottom Radius"); socket_br.prop_name = 'bottom_radius_'
            socket_tr = self.inputs.new(CQNumberSocket.bl_idname, "Top Radius"); socket_tr.prop_name = 'top_radius_'
            socket_c = self.inputs.new(CQBooleanSocket.bl_idname, "Centered"); socket_c.prop_name = 'centered_'
            self.outputs.new(CQObjectSocket.bl_idname, "Cone Object")

            # Синхронизация UI сокетов
            socket_h.default_property = self.height_
            socket_br.default_property = self.bottom_radius_
            socket_tr.default_property = self.top_radius_
            socket_c.default_property = self.centered_
            logger.debug(f"  Created sockets and synced defaults.")
        except Exception as e:
            logger.error(f"Error during socket creation/sync in {self.name}: {e}", exc_info=True)
        logger.debug(f"--- ConeNode sv_init END ---")


    # --- UI ---
    def draw_buttons(self, context, layout):
        """Draw node UI."""
        super().draw_buttons(context, layout) # Ошибки
        # Поля ввода будут нарисованы сокетами

    # --- Обработка ---
    def process(self):
        """Node's core logic."""
        logger.debug(f"--- ConeNode process START for node {self.name} ---")
        try:
            # Получаем значения
            height = self.inputs["Height"].sv_get() if self.inputs["Height"].is_linked else self.height_
            bottom_radius = self.inputs["Bottom Radius"].sv_get() if self.inputs["Bottom Radius"].is_linked else self.bottom_radius_
            top_radius = self.inputs["Top Radius"].sv_get() if self.inputs["Top Radius"].is_linked else self.top_radius_
            centered = self.inputs["Centered"].sv_get() if self.inputs["Centered"].is_linked else self.centered_

            # Проверка значений
            if height <= 0.0: raise NodeProcessingError(self, "Height must be positive.")
            if bottom_radius < 0.0: raise NodeProcessingError(self, "Bottom Radius cannot be negative.")
            if top_radius < 0.0: raise NodeProcessingError(self, "Top Radius cannot be negative.")
            if bottom_radius == 0.0 and top_radius == 0.0: raise NodeProcessingError(self, "Both radii cannot be zero.")

            logger.debug(f"  Params: H={height}, R_Bot={bottom_radius}, R_Top={top_radius}, Centered={centered}")

        except NodeProcessingError: raise
        except Exception as e:
            raise NodeProcessingError(self, f"Input error: {e}")

        # Выполняем операцию CadQuery
        try:
            MIN_RADIUS = 1e-9

            
            center_vec = cq.Vector(0, 0, 0)
            normal_vec = cq.Vector(0, 0, 1)
            
            br = bottom_radius if bottom_radius >= MIN_RADIUS else MIN_RADIUS
            tr = top_radius if top_radius >= MIN_RADIUS else MIN_RADIUS

            logger.debug("  Generating cone using loft...")
            
            bottom_circle = cq.Wire.makeCircle(br, center=center_vec, normal=normal_vec)
            top_circle = cq.Wire.makeCircle(tr, center=center_vec, normal=normal_vec)

            # Смещаем верхний круг/точку по Z
            if centered:
                 bottom_circle = bottom_circle.translate((0,0,-height/2.0))
                 top_circle = top_circle.translate((0,0, height/2.0))
            else: # Низ на 0, верх на height
                 top_circle = top_circle.translate((0,0, height))

            # Создаем тело с помощью loft
            result_shape = cq.Solid.makeLoft([bottom_circle, top_circle])

            if not result_shape or not result_shape.isValid():
                 raise NodeProcessingError(self, "Cone creation (loft) failed or resulted in invalid shape.")

            # Оборачиваем в Workplane
            result_wp = cq.Workplane("XY").add(result_shape)

            self.outputs["Cone Object"].sv_set(result_wp)
            logger.debug(f"Cone created successfully. Output is Workplane.")

        except Exception as e:
            logger.error(f"Error in ConeNode process: {e}", exc_info=True)
            raise NodeProcessingError(self, f"Cone creation failed: {e}")


# --- Регистрация ---
classes = (
    ConeNode,
)