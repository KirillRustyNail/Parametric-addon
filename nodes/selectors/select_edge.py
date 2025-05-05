# cadquery_parametric_addon/nodes/selectors/select_edge.py
import bpy
from bpy.props import IntProperty, BoolProperty, StringProperty
import logging

from ...core.node_tree import CadQueryNode
from ...core.sockets import CQObjectSocket, CQSelectorSocket, CQNumberSocket # Используем наши сокеты
from ...core.exceptions import NodeProcessingError, SocketConnectionError
from ...dependencies import cq # Нужен cq для работы с Shape

logger = logging.getLogger(__name__)

# --- Нода ---
class SelectEdgeNode(CadQueryNode):
    """Selects a specific edge from a CadQuery object by its index."""
    bl_idname = 'CQPNode_SelectorSelectEdgeNode'
    bl_label = 'Select Edge'
    sv_category = 'Selectors'

    # --- Свойства ---
    index_: IntProperty(
        name="Index", default=1, min=1, # Оставляем min=0
        description="Index of the edge to select (starting from 0)",
        update=CadQueryNode.process_node # Обновляем при изменении свойства ноды
    )
    show_marker_: BoolProperty(
        name="Show Marker", default=True,
        description="Display a visual marker for the selected edge in the 3D View",
        update=CadQueryNode.process_node # Обновляем при изменении флага
    )
    # Имя маркера (внутреннее)
    marker_object_name: StringProperty(options={'SKIP_SAVE'})

    # --- Инициализация (с prop_name и синхронизацией) ---
    def sv_init(self, context):
        logger.debug(f"--- SelectEdgeNode sv_init START for node {self.name} ---")
        logger.debug(f"  Initial index_: {self.index_}")
        try:
            self.inputs.new(CQObjectSocket.bl_idname, "Object In")
            # Создаем сокет Index
            socket_idx = self.inputs.new(CQNumberSocket.bl_idname, "Index")

            # --- Связываем свойство ноды с UI сокета через prop_name ---
            socket_idx.prop_name = 'index_' 
            # --- Синхронизируем начальное значение default_property сокета ---

            socket_idx.default_property = self.index_ # <-- Синхронизация (с float)

            # -----------------------------------------------------------------
            self.outputs.new(CQObjectSocket.bl_idname, "Object Out")
            self.outputs.new(CQSelectorSocket.bl_idname, "Selected Edge")
            logger.debug(f"  Created sockets and synced Index default: {socket_idx.default_property}")
        except Exception as e:
             logger.error(f"Error during socket creation/sync in {self.name}: {e}", exc_info=True)
        logger.debug(f"--- SelectEdgeNode sv_init END ---")

    # --- UI (только маркер и ошибки) ---
    def draw_buttons(self, context, layout):
        super().draw_buttons(context, layout) # Ошибка
        # Поле ввода индекса будет нарисовано методом draw() сокета "Index", если он не подключен
        # Оставляем только чекбокс для маркера
        layout.prop(self, "show_marker_")

    def draw_buttons_ext(self, context, layout):
        """ Draw in sidebar """
        layout.prop(self, "show_marker_")
        # Можно добавить слайдер индекса сюда, если нужно дублирование UI
        # index_socket = self.inputs.get("Index")
        # if index_socket and not index_socket.is_linked:
        #    layout.prop(self, "index_")


    # --- Очистка маркера ---
    def sv_free(self):
        """Remove marker when node is deleted."""
        if self.marker_object_name and self.marker_object_name in bpy.data.objects:
             try: bpy.data.objects.remove(bpy.data.objects[self.marker_object_name], do_unlink=True)
             except: pass

    # --- Обработка (с правильным получением индекса) ---
    def process(self):
        socket_obj = self.inputs["Object In"]
        socket_idx = self.inputs["Index"] # Получаем сокет
        out_obj_socket = self.outputs["Object Out"]
        out_sel_socket = self.outputs["Selected Edge"]

        # Очищаем предыдущий выбор и маркер по умолчанию
        out_sel_socket.sv_set(None)
        current_shape = None
        selected_index = -1 # Используем -1 как индикатор "ничего не выбрано"

        if not socket_obj.is_linked:
            update_marker(self, bpy.context, None, -1) # Скрываем маркер
            raise SocketConnectionError(self, "'Object In' must be connected")

        try:
            obj_in = socket_obj.sv_get()
            # --- Получаем индекс: из сокета (если подключен) или из свойства ноды ---
            if socket_idx.is_linked:
                 # sv_get вернет данные из кеша (может быть float или int из NumberNode)
                 index_val = socket_idx.sv_get()
            else:
                 # Берем значение из свойства ноды
                 index_val = self.index_
            # Преобразуем в int и проверяем >= 0
            index = int(round(index_val)) # Округляем float и берем целую часть
            if index < 0: index = 0 # Индекс не может быть отрицательным
            selected_index = index # Сохраняем для маркера
            # ----------------------------------------------------------------------

            if obj_in is None: raise NodeProcessingError(self, "Input object is None")

            # Получаем Shape
            if isinstance(obj_in, cq.Workplane):
                solids = obj_in.solids().vals()
                if not solids: raise NodeProcessingError(self, "Input Workplane has no solids")
                current_shape = solids[0]
                if len(solids) > 1: logger.warning(f"Node {self.name}: Input Workplane has multiple solids, selecting edge from first.")
            elif isinstance(obj_in, cq.Shape):
                current_shape = obj_in
            else:
                raise NodeProcessingError(self, f"Unsupported input type: {type(obj_in)}")

            selected_edge_object = None

            # Получаем ребра и проверяем индекс
            edges = current_shape.Edges()
            num_edges = len(edges)


            if num_edges == 0:
                 logger.warning(f"Node {self.name}: Input shape has no edges.")
                 selected_index = -1 # Сбрасываем для маркера
                 out_sel_socket.sv_set(None) # Ничего не выбрано
            elif not (0 <= index < num_edges):
                 logger.warning(f"Node {self.name}: Index {index} is out of bounds for edges (0-{num_edges-1}). No edge selected.")
                 selected_index = -1 # Сбрасываем для маркера
                 out_sel_socket.sv_set(None) # Ничего не выбрано
            else:
                  # --- Получаем сам объект ребра ---
                try:
                        selected_edge_object = edges[index] # Получаем cq.Edge
                        logger.debug(f"Node {self.name}: Selected edge object: {selected_edge_object}")
                except Exception as e:
                        logger.error(f"Failed to get edge object at index {index}: {e}")
                        selected_edge_object = None
                        selected_index = -1
                # ---------------------------------
                
            out_obj_socket.sv_set(selected_edge_object)
            # Передаем исходный объект дальше
            out_obj_socket.sv_set(obj_in)

        except Exception as e:
            update_marker(self, bpy.context, None, -1) # Скрываем маркер при ошибке
            if isinstance(e, (NodeProcessingError, SocketConnectionError)): raise
            else: raise NodeProcessingError(self, f"Processing failed: {e}")

        # Обновляем маркер в конце, после всей логики
        # Передаем current_shape, который может быть None, если была ошибка выше
        try:
             update_marker(self, bpy.context, current_shape, selected_index)
        except Exception as e_marker:
             logger.error(f"Failed to update marker for node {self.name}: {e_marker}")


# --- Регистрация ---
classes = (
    SelectEdgeNode,
)
# Регистрация оператора маркера не нужна