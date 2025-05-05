# cadquery_parametric_addon/nodes/primitives/box.py
import bpy
from bpy.props import FloatProperty, BoolProperty
import logging # Добавляем логгер

# Используем наш базовый класс и сокеты
from ...core.node_tree import CadQueryNode
from ...core.sockets import CQObjectSocket, CQNumberSocket, CQBooleanSocket
from ...core.cad_manager import cad_manager
from ...core.exceptions import NodeProcessingError

logger = logging.getLogger(__name__) # Создаем логгер

class BoxNode(CadQueryNode):
    """Creates a CadQuery Box primitive."""
    bl_idname = 'CQPNode_PrimitiveBoxNode'
    bl_label = 'Box'
    sv_category = 'Primitives'

    # --- Свойства Ноды (остаются для хранения состояния) ---
    length_: FloatProperty(
        name="Length", default=1.0, min=0.001,
        description="Box length (X axis)",
        update=CadQueryNode.process_node
    )
    width_: FloatProperty(
        name="Width", default=1.0, min=0.001,
        description="Box width (Y axis)",
        update=CadQueryNode.process_node
    )
    height_: FloatProperty(
        name="Height", default=1.0, min=0.001,
        description="Box height (Z axis)",
        update=CadQueryNode.process_node
    )

    # --- Node Setup (убираем prop_name) ---
    def sv_init(self, context):
        """Initialize sockets."""
  
        try:
            socket_l = self.inputs.new(CQNumberSocket.bl_idname, "Length"); socket_l.prop_name = 'length_' 
            socket_l.default_property = self.length_
            socket_w = self.inputs.new(CQNumberSocket.bl_idname, "Width"); socket_w.prop_name = 'width_'  
            socket_w.default_property = self.width_
            socket_h = self.inputs.new(CQNumberSocket.bl_idname, "Height"); socket_h.prop_name = 'height_' 
            socket_h.default_property = self.height_
         
            self.outputs.new(CQObjectSocket.bl_idname, "Box Object")
            
        except AttributeError as e:
             # Если у сокета нет default_property (маловероятно для этих типов)
             print(f"Error syncing socket default property: {e}")
        

    # --- UI (рисуем только ошибки) ---
    def draw_buttons(self, context, layout):
        """Draw node UI."""
        super().draw_buttons(context, layout) # Отрисовка ошибки
        # Поля ввода будут нарисованы методом draw() сокетов

    # --- Processing (изменена логика получения данных) ---
    def process(self):
        """Node's core logic."""
        # logger.debug(f"Processing node {self.name}")
        try:

            logger.debug(f"--- BoxNode process START for node {self.name} ---") # Используем logger
            logger.debug(f"  Process length_: {self.length_}")
            logger.debug(f"  Process width_: {self.width_}")
            logger.debug(f"  Process height_: {self.height_}")

            length = self.inputs["Length"].sv_get() 
            width = self.inputs["Width"].sv_get() 
            height = self.inputs["Height"].sv_get() 

            logger.debug(f"  length: {length}")
            logger.debug(f"  width: {width}")
            logger.debug(f"  height: {height}")
            
            # self.length_ = length
            # self.width_ = width 
            # self.height_ = height 

            # logger.debug("------------------------------")
            # logger.debug(f"  Process length_: {self.length_}")
            # logger.debug(f"  Process width_: {self.width_}")
            # logger.debug(f"  Process height_: {self.height_}")

            
       
            # Проверка значений
            if length <= 0: raise NodeProcessingError(self, "Length must be positive.")
            if width <= 0: raise NodeProcessingError(self, "Width must be positive.")
            if height <= 0: raise NodeProcessingError(self, "Height must be positive.")

        except NodeProcessingError: raise # Передаем наши ошибки дальше
        except Exception as e:
            # Ловим ошибки NoDataError от sv_get или другие
            raise NodeProcessingError(self, f"Input error: {e}")


        # Выполняем операцию CadQuery
        try:
            # logger.debug(f"  Executing CadQuery box({length}, {width}, {height}), centered={centered}")
            result_wp = cad_manager.execute_primitive("box", length, width, height)
            # logger.debug(f"  CadQuery result type: {type(result_wp)}")
            # Устанавливаем результат в выходной сокет
            self.outputs["Box Object"].sv_set(result_wp)
        except NotImplementedError as e:
             raise NodeProcessingError(self, str(e))
        except Exception as e:
             # Ловим и преобразуем ошибки CadQuery или другие
             raise NodeProcessingError(self, f"CadQuery failed: {e}")


# --- Registration ---
classes = (
    BoxNode,
)

# Код register/unregister убран отсюда