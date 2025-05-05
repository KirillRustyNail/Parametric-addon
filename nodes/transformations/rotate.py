# cadquery_parametric_addon/nodes/transformations/rotate.py
import bpy
from bpy.props import FloatVectorProperty, FloatProperty
import math # Для конвертации градусов в радианы

from ...core.node_tree import CadQueryNode
from ...core.sockets import CQObjectSocket, CQVectorSocket, CQNumberSocket
from ...core.exceptions import NodeProcessingError, SocketConnectionError
from ...dependencies import cq

class RotateNode(CadQueryNode):
    """Rotates a CadQuery object around a specified axis and center."""
    bl_idname = 'CQPNode_TransformationRotateNode'
    bl_label = 'Rotate'
    sv_category = 'Transformations'

    # --- Свойства Ноды ---
    # Используем углы в градусах для UI, но CQ ожидает радианы
    angle_: FloatProperty(
        name="Angle", default=0.0, subtype='ANGLE', unit='ROTATION',
        description="Angle of rotation in degrees",
        update=CadQueryNode.process_node
    )
    axis_: FloatVectorProperty(
        name="Axis", default=(0.0, 0.0, 1.0), size=3, subtype='DIRECTION',
        description="Axis of rotation (will be normalized)",
        update=CadQueryNode.process_node
    )
    center_: FloatVectorProperty(
        name="Center", default=(0.0, 0.0, 0.0), size=3, subtype='XYZ',
        description="Center point of rotation",
        update=CadQueryNode.process_node
    )

    # --- Инициализация ---
    def sv_init(self, context):
        """Initialize sockets."""
        self.inputs.new(CQObjectSocket.bl_idname, "Object In")
        self.inputs.new(CQNumberSocket.bl_idname, "Angle (deg)").prop_name = 'angle_'
        self.inputs.new(CQVectorSocket.bl_idname, "Axis").prop_name = 'axis_'
        self.inputs.new(CQVectorSocket.bl_idname, "Center").prop_name = 'center_'
        self.outputs.new(CQObjectSocket.bl_idname, "Object Out")

    # --- UI ---
    def draw_buttons(self, context, layout):
        """Draw UI."""
        super().draw_buttons(context, layout) # Ошибки
        # Поля ввода будут нарисованы сокетами, если не подключены

    # --- Обработка ---
    def process(self):
        """Node's core logic."""
        socket_obj = self.inputs["Object In"]
        socket_angle = self.inputs["Angle (deg)"]
        socket_axis = self.inputs["Axis"]
        socket_center = self.inputs["Center"]

        if not socket_obj.is_linked:
            raise SocketConnectionError(self, "'Object In' must be connected")

        # Получаем входные данные
        try:
            obj_in = socket_obj.sv_get()
            angle_deg = socket_angle.sv_get() if socket_angle.is_linked else self.angle_
            axis_vec = tuple(socket_axis.sv_get()) if socket_axis.is_linked else tuple(self.axis_)
            center_vec = tuple(socket_center.sv_get()) if socket_center.is_linked else tuple(self.center_)

            if obj_in is None: raise NodeProcessingError(self, "Input object is None")

            # Проверка вектора оси (должен быть не нулевым)
            if sum(abs(a) for a in axis_vec) < 1e-6: # Проверка на почти нулевой вектор
                 raise NodeProcessingError(self, "Rotation axis cannot be a zero vector")

        except NodeProcessingError: raise
        except Exception as e:
            raise NodeProcessingError(self, f"Input error: {e}")

        # Выполняем операцию rotate напрямую с объектом CadQuery
        try:
            if hasattr(obj_in, 'rotate'):
                # Конвертируем угол в радианы
                angle_rad = math.radians(angle_deg)
                # CQ rotate(axisStartPoint, axisEndPoint, angleDegrees)
                # Нам нужно задать ось через две точки. Используем центр и центр+ось.
                # Убедимся, что axis_vec - это cq.Vector
                axis_cq = cq.Vector(axis_vec)
                center_cq = cq.Vector(center_vec)
                # Вторая точка оси
                axis_end_point_cq = center_cq + axis_cq # Длина вектора оси не важна, только направление

                # ВНИМАНИЕ: CQ rotate принимает угол в ГРАДУСАХ! Не радианах.
                # result_obj = obj_in.rotate(center_cq, axis_end_point_cq, angle_rad)
                result_obj = obj_in.rotate(center_cq, axis_end_point_cq, angle_deg) # Используем градусы

                self.outputs["Object Out"].sv_set(result_obj)
            else:
                raise NodeProcessingError(self, f"Input object of type {type(obj_in)} does not support 'rotate'")

        except Exception as e:
            raise NodeProcessingError(self, f"Rotate operation failed: {e}")


# --- Регистрация ---
classes = (
    RotateNode,
)