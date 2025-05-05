# cadquery_parametric_addon/operators/io_json.py
import bpy
import json
import logging
from mathutils import Vector, Color, Euler, Quaternion # Импорт нужен и для экспорта, и для импорта
from bpy.props import StringProperty, BoolProperty
from bpy_extras.io_utils import ExportHelper, ImportHelper

from ...core.node_tree import CadQueryNodeTree, CadQueryNode
from ...core.sockets import CadQuerySocketBase

logger = logging.getLogger(__name__)

# --- Новые Вспомогательные функции ---

def get_serializable_value(prop_rna, value):
    """Преобразует значение свойства в JSON-совместимый формат."""
    if isinstance(value, Vector):
        return {"type": "Vector", "value": list(value)}
    elif isinstance(value, Color):
         # Сохраняем только RGB, Alpha обычно управляется отдельно, если нужно
        return {"type": "Color", "value": list(value)[:3]}
    elif isinstance(value, Euler):
        return {"type": "Euler", "value": list(value)}
    elif isinstance(value, Quaternion):
        return {"type": "Quaternion", "value": list(value)}
    elif isinstance(value, bpy.types.bpy_prop_array):
         # Другие массивы (IntVectorProperty и т.д.) сохраняем как простой список
         # Или можно добавить свои типы, например {"type": "IntVector", "value": ...}
        return list(value)
    elif isinstance(prop_rna, bpy.types.EnumProperty):
        return str(value) # Сохраняем Enum как строку
    elif isinstance(value, (str, int, float, bool, list, tuple, dict, type(None))):
        return value # Базовые типы сохраняем как есть
    else:
        logger.warning(f"Cannot serialize property value of type {type(value)}. Returning None.")
        return None

def node_to_dict_v2(node: CadQueryNode) -> dict:
    """Сериализует ноду в словарь (версия 2)."""
    node_dict = {
        "bl_idname": node.bl_idname,
        "name": node.name, # Используем как временный ID при импорте
        "label": node.label,
        "location": tuple(node.location), # Сохраняем исходное положение
        "width": node.width,
        "height": node.height,
        "hide": node.hide,
        "mute": node.mute,
        "properties": {},
    }

    try:
        cls_annotations = node.__class__.__annotations__
    except AttributeError:
        cls_annotations = {}

    for prop_id, prop_obj in cls_annotations.items():
        is_bpy_prop = False
        registered_prop = getattr(node.__class__, prop_id, None)
        if isinstance(prop_obj, bpy.props._PropertyDeferred):
            is_bpy_prop = True
        elif isinstance(registered_prop, bpy.types.Property):
            is_bpy_prop = True

        if is_bpy_prop:
            if prop_id.startswith("_") or prop_id in ['n_id', 'tree_id_memory', 'rna_type']: continue
            try:
                value = getattr(node, prop_id)
                prop_rna = node.bl_rna.properties.get(prop_id) # Получаем RNA свойства
                if prop_rna:
                     serializable_value = get_serializable_value(prop_rna, value)
                     if serializable_value is not None:
                          node_dict["properties"][prop_id] = serializable_value
                # else: logger.warning(f"Could not get RNA for property '{prop_id}' on node '{node.name}'.")

            except AttributeError: logger.warning(f"Could not get property '{prop_id}' from node '{node.name}'")
            except Exception as e: logger.error(f"Error getting/serializing property '{prop_id}' from node '{node.name}': {e}")

    return node_dict

def tree_to_dict_v2(tree: CadQueryNodeTree) -> dict:
    """Сериализует дерево нод в словарь (версия 2)."""
    tree_dict = {
        "bl_idname": tree.bl_idname, # Тип дерева
        "name": tree.name,          # Имя дерева (для информации)
        "nodes": [],
        "links": []
    }
    node_name_map = {} # name -> node_data (для разрешения связей)
    for node in tree.nodes:
        if isinstance(node, CadQueryNode):
            node_data = node_to_dict_v2(node)
            tree_dict["nodes"].append(node_data)
            node_name_map[node.name] = node_data # Сохраняем ссылку на данные ноды

    for link in tree.links:
        from_node = link.from_node
        to_node = link.to_node
        # Проверяем, что обе ноды были экспортированы
        if from_node.name in node_name_map and to_node.name in node_name_map:
            from_socket = link.from_socket
            to_socket = link.to_socket
            # Проверяем, что сокеты существуют (на всякий случай)
            if from_socket and to_socket:
                link_dict = {
                    "from_node": from_node.name, # Используем имя как ID
                    "from_socket": from_socket.name,
                    "to_node": to_node.name,
                    "to_socket": to_socket.name,
                }
                tree_dict["links"].append(link_dict)
            # else: logger.warning(f"Link skipped: sockets not found for link {link}")
        # else: logger.warning(f"Link skipped: nodes {from_node.name} or {to_node.name} not exported.")

    return tree_dict

def get_value_from_dict(data):
    """Преобразует словарь {"type": T, "value": V} обратно в объект mathutils или возвращает V."""
    if isinstance(data, dict) and "type" in data and "value" in data:
        type_str = data["type"]
        value = data["value"]
        try:
            if type_str == "Vector": return Vector(value)
            elif type_str == "Color": return Color(value) # Color ожидает 3 значения
            elif type_str == "Euler": return Euler(value)
            elif type_str == "Quaternion": return Quaternion(value)
            else:
                logger.warning(f"Unknown serialized type '{type_str}'. Returning raw value.")
                return value
        except Exception as e:
            logger.error(f"Failed to convert serialized type '{type_str}' with value {value}: {e}")
            return value # Возвращаем исходное значение при ошибке конвертации
    # Если это не наш специальный словарь, возвращаем как есть
    return data


# --- Оператор Экспорта (Использует новые функции) ---
class CQP_OT_ExportJsonV2(bpy.types.Operator, ExportHelper):
    """Export the active CadQuery Node Tree to a JSON file (V2 Format)"""
    bl_idname = "cqp.export_json_v2" # Новый ID
    bl_label = "Export CadQuery Tree (JSON V2)"
    bl_options = {'PRESET', 'UNDO'}

    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return (space and space.type == 'NODE_EDITOR' and
                space.node_tree and isinstance(space.node_tree, CadQueryNodeTree))

    def execute(self, context):
        node_tree = context.space_data.node_tree
        if not node_tree:
            self.report({'ERROR'}, "No active CadQuery Node Tree found."); return {'CANCELLED'}
        logger.info(f"Exporting Node Tree '{node_tree.name}' to {self.filepath} (V2)")
        try:
            tree_data = tree_to_dict_v2(node_tree) # Используем новую функцию
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(tree_data, f, indent=2, ensure_ascii=False) # indent=2 для компактности
            logger.info("Export V2 successful.")
            self.report({'INFO'}, f"Exported tree to {self.filepath}")
        except Exception as e:
            logger.error(f"Export V2 failed: {e}", exc_info=True)
            self.report({'ERROR'}, f"Export V2 failed: {e}"); return {'CANCELLED'}
        return {'FINISHED'}


# --- Оператор Импорта (V2, с добавлением и синхронизацией UI сокета) ---
class CQP_OT_ImportJsonV2(bpy.types.Operator, ImportHelper):
    """Import and add nodes from a JSON file to the active CadQuery Node Tree (V2 Format)"""
    bl_idname = "cqp.import_json_v2"
    bl_label = "Import CadQuery Tree (JSON V2)"
    bl_options = {'PRESET', 'UNDO'}

    filename_ext = ".json"; filter_glob: StringProperty(default="*.json", options={'HIDDEN'})
    offset_nodes: BoolProperty(name="Offset Imported Nodes", default=True)

    @classmethod
    def poll(cls, context):
        return context.space_data and context.space_data.type == 'NODE_EDITOR'

    def execute(self, context):
        target_tree = context.space_data.node_tree
        if not target_tree or not isinstance(target_tree, CadQueryNodeTree):
            self.report({'WARNING'}, "No active CadQuery Node Tree."); return {'CANCELLED'}

        logger.info(f"Importing nodes from {self.filepath} into tree '{target_tree.name}' (V2)")
        # Чтение файла
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f: tree_data = json.load(f)
            if tree_data.get("bl_idname") != CadQueryNodeTree.bl_idname: logger.warning(f"JSON may be for different tree type ({tree_data.get('bl_idname')}).")
        except Exception as e: logger.error(f"Error reading file: {e}", exc_info=True); self.report({'ERROR'}, f"Error reading file: {e}"); return {'CANCELLED'}

        nodes_data = tree_data.get("nodes", []); links_data = tree_data.get("links", [])
        if not nodes_data: self.report({'WARNING'}, "JSON has no node data."); return {'CANCELLED'}

        try:
            # --- Устанавливаем флаг импорта и отключаем обновление ---
            target_tree["_is_importing"] = True; logger.debug("Set _is_importing flag.")
            was_processing = target_tree.sv_process; target_tree.sv_process = False; logger.debug("Disabled tree processing.")
            # -------------------------------------------------------

            # --- Определяем смещение ---
            offset = Vector((0.0, 0.0))
            if self.offset_nodes and hasattr(context, "cursor_location"):
                 offset = context.cursor_location; avg_loc = Vector((0.0, 0.0)); valid_locs = 0
                 for node_data in nodes_data:
                      loc = node_data.get("location");
                      if loc and isinstance(loc, list) and len(loc) == 2: avg_loc += Vector(loc); valid_locs += 1
                 if valid_locs > 0: avg_loc /= valid_locs; offset -= avg_loc
            # ---------------------------

            created_nodes_map = {} # {json_name: actual_node}
            # --- Создание нод ---
            logger.debug(f"Importing {len(nodes_data)} nodes...")
            for node_data in nodes_data:
                node_idname = node_data.get("bl_idname"); original_name = node_data.get("name")
                if not node_idname or not original_name: continue

                try:
                    new_node = target_tree.nodes.new(type=node_idname)
                    # Генерация уникального имени
                    new_node_name = original_name; count = 1
                    while new_node_name in target_tree.nodes: new_node_name = f"{original_name}.{count:03d}"; count += 1
                    new_node.name = new_node_name

                    new_node.label = node_data.get("label", ""); loc = node_data.get("location")
                    new_node.location = Vector(loc) + offset if loc else offset
                    new_node.width = node_data.get("width", new_node.width); new_node.height = node_data.get("height", new_node.height)
                    new_node.hide = node_data.get("hide", False); new_node.mute = node_data.get("mute", False)

                    # --- Устанавливаем свойства ноды и синхронизируем UI сокета ---
                    logger.debug(f"  Setting properties for node '{new_node_name}' (original: '{original_name}')")
                    for prop_id, value_data in node_data.get("properties", {}).items():
                        if hasattr(new_node, prop_id):
                            try:
                                final_value = get_value_from_dict(value_data) # Преобразуем из JSON
                                setattr(new_node, prop_id, final_value) # Устанавливаем свойство ноды
                                # logger.debug(f"    Set node prop {prop_id} = {final_value}")

                                # Ищем сокет и синхронизируем его default_property для UI
                                corresponding_socket = None
                                for input_socket in new_node.inputs:
                                    sock_prop_name = getattr(input_socket, 'prop_name', None)
                                    if sock_prop_name == prop_id: corresponding_socket = input_socket; break

                                if corresponding_socket and hasattr(corresponding_socket, 'default_property'):
                                    try:
                                        # Используем final_value, которое уже преобразовано
                                        socket_value_to_set = final_value
                                        # Преобразуем в tuple для свойств сокета типа Vector/Color и т.д.
                                        if isinstance(final_value, (Vector, Color, Euler, Quaternion)):
                                            socket_value_to_set = tuple(final_value)

                                        # Проверка типа перед присваиванием сокету (избегаем ошибок)
                                        socket_prop = getattr(corresponding_socket, 'default_property', None)
                                        if isinstance(socket_prop, bpy.types.bpy_prop_array) and not isinstance(socket_value_to_set, (list, tuple)):
                                             logger.warning(f"      Type mismatch for socket UI sync: node prop '{prop_id}', socket '{corresponding_socket.name}'. Skipping socket update.")
                                        else:
                                             corresponding_socket.default_property = socket_value_to_set
                                             # logger.debug(f"      Synced socket '{corresponding_socket.name}' UI to: {socket_value_to_set}")
                                    except Exception as e_sock_set: logger.warning(f"      Failed to sync UI for socket linked to '{prop_id}': {e_sock_set}")

                            except Exception as e_prop: logger.error(f"    Failed to set property '{prop_id}' on node '{new_node_name}': {e_prop}", exc_info=True)
                        # else: logger.warning(f"    Property '{prop_id}' not found on new node '{new_node_name}'.")
                    # -------------------------------------------------------------
                    created_nodes_map[original_name] = new_node # Используем оригинальное имя как ключ

                except Exception as e_node: logger.error(f"Error creating node '{original_name}': {e_node}", exc_info=True)

            # --- Создание связей ---
            logger.debug(f"Creating {len(links_data)} links...")
            for link_data in links_data:
                from_node_name = link_data.get("from_node"); from_sock_name = link_data.get("from_socket")
                to_node_name = link_data.get("to_node"); to_sock_name = link_data.get("to_socket")
                if not all([from_node_name, from_sock_name, to_node_name, to_sock_name]): continue

                from_node = created_nodes_map.get(from_node_name) # Ищем по оригинальному имени
                to_node = created_nodes_map.get(to_node_name)     # Ищем по оригинальному имени
                if not from_node or not to_node: continue

                from_socket = from_node.outputs.get(from_sock_name); to_socket = to_node.inputs.get(to_sock_name)
                if not from_socket or not to_socket: continue

                try: target_tree.links.new(from_socket, to_socket)
                except Exception as e_link: logger.error(f"Failed to create link: {e_link}")

            # --- Восстанавливаем состояние обновления ---
            if "_is_importing" in target_tree: del target_tree["_is_importing"]; logger.debug("Removed _is_importing flag.")
            target_tree.sv_process = was_processing; logger.debug(f"Restored sv_process: {was_processing}")
            # -------------------------------------------

            if target_tree.sv_process:
                from ...core.update_system import update_manager
                logger.info(f"Requesting update for tree '{target_tree.name}' after import")
                state = update_manager.get_tree_state(target_tree)
                state.mark_all_dirty()
                update_manager.request_update(target_tree)

            logger.info(f"Import successful into tree '{target_tree.name}'.")
            self.report({'INFO'}, f"Imported nodes into tree '{target_tree.name}'")

        except Exception as e:
            if target_tree and "_is_importing" in target_tree: del target_tree["_is_importing"]
            logger.error(f"Import failed: {e}", exc_info=True)
            self.report({'ERROR'}, f"Import failed: {e}")
            # Не удаляем ноды, так как добавляли в существующее дерево
            return {'CANCELLED'}

        return {'FINISHED'}


# --- Регистрация ---
classes = (
    CQP_OT_ExportJsonV2, # Регистрируем новые операторы
    CQP_OT_ImportJsonV2,
)

def register():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)

def unregister():
    from bpy.utils import unregister_class
    for cls in reversed(classes):
        try: unregister_class(cls)
        except RuntimeError: logger.warning(f"Could not unregister operator class: {cls.__name__}")