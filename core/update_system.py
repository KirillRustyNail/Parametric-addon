# cadquery_parametric_addon/core/update_system.py
import bpy
import time
import logging
import traceback
from collections import defaultdict
from graphlib import TopologicalSorter

from .exceptions import NodeProcessingError, DependencyError, CadQueryExecutionError # Добавляем CadQueryExecutionError
from .constants import UPDATE_KEY, ERROR_KEY, ERROR_STACK_KEY

logger = logging.getLogger(__name__)

class UpdateTreeState:
    """Holds the state and structure of a single node tree for update purposes."""
    def __init__(self, tree):
        self.tree = tree
        self.nodes: dict[str, bpy.types.Node] = {}
        self.dependencies: dict[str, set[str]] = defaultdict(set)
        self.execution_order: list[str] = [] # Порядок выполнения нод
        self.dirty_nodes: set[str] = set()
        self.needs_rebuild = True
        # Сразу помечаем все ноды как грязные при создании состояния
        # self.mark_all_dirty() # Делаем это при первом запросе на обновление
        # logger.debug(f"[{self.tree.name}] Initialized state, needs rebuild.")

    def _clear_node_states(self, node_names: list[str]):
        """Сбрасывает состояние ошибки/обновления для указанных нод."""
        for node_name in node_names:
             node = self.nodes.get(node_name)
             if not node: continue
             if ERROR_KEY in node: del node[ERROR_KEY]
             if ERROR_STACK_KEY in node: del node[ERROR_STACK_KEY]
             node[UPDATE_KEY] = False # Считаем не обновленной перед запуском

    def _build_graph_and_order(self):
        """Builds the dependency graph and determines execution order."""
        self.nodes.clear()
        self.dependencies.clear()
        logger.debug(f"[{self.tree.name}] Rebuilding dependency graph and execution order...")

        active_nodes = {node.name: node for node in self.tree.nodes if not node.mute}
        self.nodes = active_nodes

        # Строим зависимости
        temp_deps = defaultdict(set)
        for node_name, node in active_nodes.items():
            # Сразу добавляем узел в граф
            temp_deps[node_name] # = set()
            for input_socket in node.inputs:
                if input_socket.is_linked:
                    for link in input_socket.links:
                        from_node = link.from_node
                        if from_node.name in active_nodes:
                            temp_deps[node_name].add(from_node.name)

        self.dependencies = temp_deps

        # Определяем порядок выполнения через топологическую сортировку
        try:
            sorter = TopologicalSorter(self.dependencies)
            self.execution_order = list(sorter.static_order())
            logger.debug(f"[{self.tree.name}] New execution order: {self.execution_order}")
        except Exception as e:
            logger.error(f"[{self.tree.name}] Topological sort failed during rebuild: {e}. Graph might have cycles.", exc_info=True)
            self.execution_order = list(active_nodes.keys()) # Запасной вариант - не сортированный

        self.needs_rebuild = False

    def mark_dirty(self, node_names: list[str]):
        """Marks specific nodes and triggers rebuild if needed."""
        # logger.debug(f"[{self.tree.name}] Marking nodes dirty: {node_names}")
        newly_dirty = set(node_names) & set(self.nodes.keys()) # Только существующие ноды
        if newly_dirty:
             self.dirty_nodes.update(newly_dirty)
        # Если граф нужно перестроить, перестраиваем сразу или при get_nodes_to_process?
        # Лучше при get_nodes_to_process, чтобы не делать это на каждое изменение свойства

    def mark_all_dirty(self):
         """Marks all nodes as dirty."""
         logger.debug(f"[{self.tree.name}] Marking all nodes dirty.")
         self.dirty_nodes = set(self.nodes.keys())

    def get_processing_list(self) -> list[str]:
         """Возвращает список нод для обработки в правильном порядке."""
         if self.needs_rebuild:
             self._build_graph_and_order()
             # После перестройки графа нужно пересчитать все ноды? Да.
             self.mark_all_dirty()
             logger.debug(f"[{self.tree.name}] Graph rebuilt, marked all nodes dirty.")

         if not self.dirty_nodes:
             # logger.debug(f"[{self.tree.name}] No dirty nodes to process.")
             return []

         # --- Логика определения нод для обновления ---
         # 1. Начинаем с "грязных" нод.
         # 2. Идем по графу зависимостей ВНИЗ (downstream). Все ноды ниже по течению от грязных тоже надо обновить.
         # 3. Используем полный порядок выполнения (self.execution_order) как основу.
         # 4. Фильтруем execution_order, оставляя только те ноды, которые:
         #    а) Сами "грязные".
         #    б) Зависят (прямо или косвенно) от "грязных" нод.

         nodes_to_evaluate = set()
         queue = list(self.dirty_nodes)
         visited_downstream = set()

         # Строим обратные зависимости (кто зависит от key?)
         reverse_deps = defaultdict(set)
         for node_name, deps in self.dependencies.items():
            for dep_name in deps:
                reverse_deps[dep_name].add(node_name)

         # Обход вниз по течению от грязных нод
         while queue:
             node_name = queue.pop(0)
             if node_name not in self.nodes: continue
             if node_name not in visited_downstream:
                  visited_downstream.add(node_name)
                  nodes_to_evaluate.add(node_name) # Добавляем текущую
                  # Добавляем в очередь тех, кто зависит от текущей ноды
                  for dependent_node in reverse_deps.get(node_name, set()):
                       if dependent_node not in visited_downstream:
                            queue.append(dependent_node)

         # Теперь у нас есть все ноды, которые нужно пересчитать (грязные + зависимые от них)
         # Фильтруем полный порядок выполнения, оставляя только нужные ноды
         processing_list = [name for name in self.execution_order if name in nodes_to_evaluate]
         logger.debug(f"[{self.tree.name}] Nodes to process this cycle: {processing_list}")

         # Сбрасываем состояние только для тех нод, что будем обрабатывать
         self._clear_node_states(processing_list)

         return processing_list


    def process_node(self, node_name: str):
        """Processes a single node, checking input readiness."""
        node = self.nodes.get(node_name)
        if not node:
            logger.warning(f"[{self.tree.name}] Node '{node_name}' not found during processing.")
            return False # Сигнал об ошибке

        # --- Проверка готовности входов ---
        inputs_ready = True
        for dep_name in self.dependencies.get(node_name, set()):
            dep_node = self.nodes.get(dep_name)
            if not dep_node:
                logger.warning(f"[{self.tree.name}] Dependency '{dep_name}' for node '{node_name}' not found.")
                # Считаем вход неготовым, если зависимость пропала
                inputs_ready = False
                break
            # Проверяем флаг UPDATE_KEY зависимости
            if not dep_node.get(UPDATE_KEY, False):
                 logger.debug(f"  Dependency '{dep_name}' for '{node_name}' is not updated. Skipping '{node_name}'.")
                 inputs_ready = False
                 break

        if not inputs_ready:
            # Важно: НЕ устанавливаем ошибку. Просто пропускаем.
            # Нода останется с UPDATE_KEY=False
            # Очищаем старую ошибку, если она была
            # if ERROR_KEY in node: del node[ERROR_KEY]
            # if ERROR_STACK_KEY in node: del node[ERROR_STACK_KEY]
            return True # Пропуск - это не ошибка обработки

        # --- Выполнение process() ноды ---
        logger.debug(f"Executing process() for node {node_name}")
        try:
            # Проверка на DependencyError ноды
            if hasattr(node, 'dependency_error') and node.dependency_error:
                 raise node.dependency_error

            # Очищаем ошибку перед выполнением
            node.set_error(None)

            start_time = time.perf_counter()
            node.process() # <--- Основной вызов
            end_time = time.perf_counter()

            # Успех - ставим флаг обновления
            node[UPDATE_KEY] = True
            # logger.debug(f"Node {node_name} processed successfully in {end_time - start_time:.4f}s.")
            return True

        except Exception as e:
            logger.error(f"[{self.tree.name}] Error processing node '{node_name}': {e}", exc_info=False)
            stack = traceback.format_exc()
            # Преобразуем исключение и сохраняем в ноде
            error_msg = ""
            if isinstance(e, (NodeProcessingError, DependencyError, CadQueryExecutionError)):
                 error_msg = str(e)
            else:
                 error_msg = f"Unexpected error: {e}"

            node.set_error(error_msg, stack)
            # Нода не обновилась успешно
            node[UPDATE_KEY] = False
            return False # Сигнал об ошибке


class UpdateManager:
    """Manages the update process for all CadQuery node trees."""
    def __init__(self):
        self.tree_states: dict[str, UpdateTreeState] = {} # tree.name -> state
        self.update_queue: set[str] = set() # Имена деревьев в очереди
        self.is_updating = False

    def get_tree_state(self, tree: bpy.types.NodeTree) -> UpdateTreeState:
        """Gets or creates the state object for a given tree."""
        state = self.tree_states.get(tree.name)
        if state is None or state.tree != tree: # Проверяем, не изменился ли объект дерева
            logger.info(f"Creating/Updating UpdateTreeState for tree '{tree.name}'")
            state = UpdateTreeState(tree)
            self.tree_states[tree.name] = state
            state.needs_rebuild = True # Новое или измененное дерево требует перестройки
        return state

    def mark_tree_dirty(self, tree: bpy.types.NodeTree):
        """Marks the tree structure as potentially changed."""
        state = self.get_tree_state(tree)
        state.needs_rebuild = True
        # Не помечаем все ноды грязными здесь, сделаем это в request_update/run_update
        logger.debug(f"Tree '{tree.name}' marked for graph rebuild.")


    def mark_nodes_dirty(self, tree: bpy.types.NodeTree, nodes: list[bpy.types.Node]):
        """Marks specific nodes in a tree as dirty."""
        if not nodes: return
        state = self.get_tree_state(tree)
        node_names = [n.name for n in nodes]
        state.mark_dirty(node_names)
        # logger.debug(f"Nodes marked dirty in '{tree.name}': {node_names}")


    def request_update(self, tree: bpy.types.NodeTree):
        """Adds a tree to the update queue if needed."""
        if not hasattr(tree, 'sv_process') or not tree.sv_process:
             # logger.debug(f"Update requested for inactive tree '{tree.name}', skipping.")
             return

        state = self.get_tree_state(tree)
        # Добавляем в очередь, если есть грязные ноды ИЛИ если граф нужно перестроить
        if state.dirty_nodes or state.needs_rebuild:
            if tree.name not in self.update_queue:
                 logger.debug(f"Tree '{tree.name}' added to update queue (Dirty: {bool(state.dirty_nodes)}, Rebuild: {state.needs_rebuild}).")
                 self.update_queue.add(tree.name)
                 if not self.is_updating:
                     # Запускаем цикл обновления через таймер
                     bpy.app.timers.register(self.run_update_cycle, first_interval=0.001)


    def run_update_cycle(self):
        """Processes all trees currently in the update queue."""
        if self.is_updating: return None # Защита от рекурсии
        if not self.update_queue: return None # Остановка таймера

        self.is_updating = True
        logger.info(f"--- Starting Update Cycle (Queue: {self.update_queue}) ---")
        start_total_time = time.perf_counter()

        trees_to_process = list(self.update_queue)
        self.update_queue.clear()

        processed_ok = True # Флаг общего успеха

        for tree_name in trees_to_process:
            # --- Получение дерева и состояния ---
            if tree_name not in bpy.data.node_groups:
                logger.warning(f"Tree '{tree_name}' not found, removing from states.")
                if tree_name in self.tree_states: del self.tree_states[tree_name]
                continue
            tree = bpy.data.node_groups[tree_name]
            if not hasattr(tree, 'sv_process') or not tree.sv_process:
                logger.debug(f"Skipping update for inactive tree '{tree_name}'.")
                # Очищаем грязные флаги, если дерево неактивно? Да.
                if tree_name in self.tree_states:
                     self.tree_states[tree_name].dirty_nodes.clear()
                continue
            state = self.get_tree_state(tree)

            # --- Получение списка нод для обработки ---
            processing_list = state.get_processing_list()
            if not processing_list:
                 logger.debug(f"No nodes need processing in tree '{tree_name}'.")
                 state.dirty_nodes.clear() # Очищаем, раз обрабатывать не нужно
                 continue

            # --- Обработка нод ---
            logger.info(f"Processing tree '{tree_name}' ({len(processing_list)} nodes)...")
            start_tree_time = time.perf_counter()
            tree_had_errors = False
            for node_name in processing_list:
                 success = state.process_node(node_name)
                 if not success:
                      tree_had_errors = True
                      # Прерывать ли обработку дерева при первой ошибке?
                      # Пока нет, чтобы увидеть все ошибки. Но зависимые ноды не выполнятся.
            end_tree_time = time.perf_counter()
            logger.info(f"Tree '{tree_name}' processed in {end_tree_time - start_tree_time:.4f}s." + (" (with errors)" if tree_had_errors else ""))

            # --- Обновление UI дерева (опционально) ---
            if hasattr(tree, 'update_ui'):
                 # Собираем ошибки для UI
                 node_errors = [{
                    'error': state.nodes[n_name].get(ERROR_KEY),
                    'stack': state.nodes[n_name].get(ERROR_STACK_KEY)
                 } if n_name in state.nodes else {'error':None, 'stack':None}
                 for n_name in [n.name for n in tree.nodes]] # Порядок важен для UI

                 try:
                      tree.update_ui(node_errors)
                 except Exception as ui_err:
                      logger.error(f"Error during UI update for tree '{tree_name}': {ui_err}", exc_info=True)


            # Очищаем грязные ноды ПОСЛЕ успешной обработки (или даже если были ошибки?)
            # Лучше очищать всегда, чтобы не зациклиться на одной ошибке.
            state.dirty_nodes.clear()

        end_total_time = time.perf_counter()
        logger.info(f"--- Update Cycle Finished in {end_total_time - start_total_time:.4f}s ---")
        self.is_updating = False

        # Перезапускаем таймер, если появились новые запросы
        if self.update_queue:
            bpy.app.timers.register(self.run_update_cycle, first_interval=0.001)
            return None

        return None # Остановить таймер


    def clear_all_states(self):
        """Clears the state for all trees."""
        logger.info("Clearing all tree update states.")
        self.tree_states.clear()
        self.update_queue.clear()
        self.is_updating = False


# Глобальный экземпляр
update_manager = UpdateManager()