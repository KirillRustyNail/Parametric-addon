# cadquery_parametric_addon/nodes/selectors/select_edge.py
import bpy
from bpy.props import IntProperty, BoolProperty, StringProperty # Bool/String убраны, но импорт оставим на всякий случай
import logging

from ...core.node_tree import CadQueryNode
from ...core.sockets import CQObjectSocket, CQSelectorSocket, CQNumberSocket, CQIntSocket # Используем CQIntSocket
from ...core.exceptions import NodeProcessingError, SocketConnectionError
from ...dependencies import cq # Нужен cq для работы с Shape

logger = logging.getLogger(__name__)

# --- Вспомогательная функция для маркера УДАЛЕНА ---
# def update_marker(node, context, shape, edge_index):
#    ...

# --- Нода ---
class SelectEdgeNode(CadQueryNode):
    """Selects a specific edge object from a CadQuery shape by its index."""
    bl_idname = 'CQPNode_SelectorSelectEdgeNode'
    bl_label = 'Select Edge'
    sv_category = 'Selectors'

    # --- Свойства ---
    index_: IntProperty(
        name="Index", default=0, min=0,
        description="Index of the edge to select (starting from 0)",
        update=CadQueryNode.process_node
    )
    # --- show_marker_ и marker_object_name УДАЛЕНЫ ---

    # --- Инициализация (с prop_name и синхронизацией) ---
    def sv_init(self, context):
        logger.debug(f"--- SelectEdgeNode sv_init START for node {self.name} ---")
        logger.debug(f"  Initial index_: {self.index_}")
        try:
            self.inputs.new(CQObjectSocket.bl_idname, "Object In")
            # Используем CQIntSocket
            socket_idx = self.inputs.new(CQIntSocket.bl_idname, "Index") # <-- Используем IntSocket
            socket_idx.prop_name = 'index_' # Связываем со свойством ноды для обновления через UI сокета
            # Синхронизируем IntProperty сокета с IntProperty ноды
            socket_idx.default_property = self.index_ # <-- Синхронизация int -> int
            self.outputs.new(CQObjectSocket.bl_idname, "Object Out")
            self.outputs.new(CQSelectorSocket.bl_idname, "Selected Edge") # Передаем cq.Edge
            logger.debug(f"  Created sockets and synced Index default: {socket_idx.default_property}")
        except Exception as e:
             logger.error(f"Error during socket creation/sync in {self.name}: {e}", exc_info=True)
        logger.debug(f"--- SelectEdgeNode sv_init END ---")

    # --- UI (только ошибки) ---
    def draw_buttons(self, context, layout):
        super().draw_buttons(context, layout) # Ошибка
        # Поле ввода индекса будет нарисовано методом draw() сокета "Index", если он не подключен

    # --- Очистка (ничего не делаем) ---
    def sv_free(self):
        pass # Маркеров нет

    # --- Обработка (с проверкой сокетов и без маркеров) ---
    def process(self):
        # --- Получаем сокеты БЕЗОПАСНО ---
        socket_obj = self.inputs.get("Object In")
        socket_idx = self.inputs.get("Index")
        out_obj_socket = self.outputs.get("Object Out")
        out_sel_socket = self.outputs.get("Selected Edge")

        # --- Проверяем существование КЛЮЧЕВЫХ сокетов ---
        if not socket_obj or not socket_idx or not out_obj_socket or not out_sel_socket:
            logger.warning(f"Node {self.name}: Sockets not fully initialized yet. Skipping process.")
            # Сбрасываем выходы на всякий случай, если они уже существуют
            if out_sel_socket: out_sel_socket.sv_set(None)
            if out_obj_socket: out_obj_socket.sv_set(None)
            return # Просто пропускаем этот цикл обновления
        # -------------------------------------------------

        # Сбрасываем выход селектора перед обработкой
        out_sel_socket.sv_set(None)
        selected_edge_object = None
        obj_in = None # Инициализируем на случай ошибки до получения obj_in

        try:
            if not socket_obj.is_linked:
                raise SocketConnectionError(self, "'Object In' must be connected")

            obj_in = socket_obj.sv_get() # Получаем объект CQ

            # --- Получаем индекс (int) ---
            if socket_idx.is_linked:
                index_val = socket_idx.sv_get()
                try: index = int(round(index_val))
                except: raise NodeProcessingError(self, f"Invalid index value received: {index_val}")
            else:
                index = self.index_ # Берем из свойства ноды (уже int)
            if index < 0: index = 0 # Убедимся, что не отрицательный
            # ---------------------------

            if obj_in is None: raise NodeProcessingError(self, "Input object is None")

            # Получаем Shape
            current_shape = None
            if isinstance(obj_in, cq.Workplane):
                # logger.debug(f"Node {self.name}: Input is Workplane, extracting solids.")
                solids = obj_in.solids().vals()
                if not solids: raise NodeProcessingError(self, "Input Workplane has no solids")
                current_shape = solids[0]
                # if len(solids) > 1: logger.warning(...)
            elif isinstance(obj_in, cq.Shape):
                # logger.debug(f"Node {self.name}: Input is Shape.")
                current_shape = obj_in
            else:
                raise NodeProcessingError(self, f"Unsupported input type: {type(obj_in)}")

            # Получаем ребра и выбранное ребро
            edges = current_shape.Edges()
            num_edges = len(edges)
            # logger.debug(f"Node {self.name}: Found {num_edges} edges. Requesting index {index}.")

            if num_edges == 0: logger.warning(f"Node {self.name}: Input shape has no edges.")
            elif not (0 <= index < num_edges): logger.warning(f"Node {self.name}: Index {index} out of bounds (0-{num_edges-1}).")
            else:
                try:
                    selected_edge_object = edges[index] # Получаем cq.Edge
                    # logger.debug(f"Node {self.name}: Successfully selected edge index {index}")
                except Exception as e:
                    logger.error(f"Node {self.name}: Failed to get edge object at index {index}: {e}")
                    selected_edge_object = None # Сбрасываем, если ошибка

            # Передаем объект ребра или None
            out_sel_socket.sv_set(selected_edge_object)
            # Передаем исходный объект дальше (даже если ребро не выбрано)
            out_obj_socket.sv_set(obj_in)

        except Exception as e:
            # Сбрасываем выходы при ошибке
            out_sel_socket.sv_set(None)
            out_obj_socket.sv_set(None) # Не передаем объект дальше при ошибке
            # Передаем ошибку системе обновления
            if isinstance(e, (NodeProcessingError, SocketConnectionError)): raise
            else:
                 # Логируем полную ошибку для отладки
                 logger.error(f"Unexpected error in SelectEdgeNode process for node '{self.name}': {e}", exc_info=True)
                 raise NodeProcessingError(self, f"Processing failed: {e}")

        # Логика маркеров удалена

# --- Регистрация ---
classes = (
    SelectEdgeNode,
)
# Регистрация в registration.py