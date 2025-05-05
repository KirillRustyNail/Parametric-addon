# cadquery_parametric_addon/nodes/io/viewer.py
import bpy
from bpy.props import StringProperty
import logging

from ...core.node_tree import CadQueryNode
from ...core.sockets import CQObjectSocket
from ...utils import cq_utils # Утилиты конвертации
from ...core.exceptions import NodeProcessingError, ViewerError, SocketConnectionError
from ...dependencies import cq # Нужен доступ к типам CadQuery

logger = logging.getLogger(__name__)

class ViewerNode(CadQueryNode):
    """Displays the result of a CadQuery operation in the Blender scene."""
    bl_idname = 'CQPNode_IOViewerNode'
    bl_label = 'Viewer'
    sv_category = 'Input/Output'

    # --- Properties ---
    # Храним имя объекта, а не указатель, т.к. указатель может стать невалидным
    target_object_name: StringProperty(
        name="Target Object Name",
        description="Name of the Blender object created/updated by this node",
        default=""
    )

    # --- Node Setup ---
    def sv_init(self, context):
        """Initialize sockets."""
        self.inputs.new(CQObjectSocket.bl_idname, "Object In")

    def draw_buttons(self, context, layout):
        """Draw node UI."""
        super().draw_buttons(context, layout) # Показать ошибки
        layout.prop(self, "target_object_name", text="Output Name")

    # --- Cleanup ---
    def clear_object(self):
        """Removes the associated Blender object and mesh."""
        obj_name = self.target_object_name # Берем имя из свойства
        if obj_name and obj_name in bpy.data.objects:
            obj = bpy.data.objects[obj_name]
            mesh = obj.data
            logger.debug(f"Clearing object: Removing Blender object '{obj_name}' and mesh '{mesh.name if mesh else 'None'}'")
            try:
                bpy.data.objects.remove(obj, do_unlink=True)
                # Удаляем меш, только если на него больше нет ссылок
                if mesh and mesh.users == 0:
                    logger.debug(f"Removing unused mesh '{mesh.name}' during clear.")
                    bpy.data.meshes.remove(mesh, do_unlink=True)
            except Exception as e:
                logger.error(f"Error during object/mesh removal in clear_object for '{obj_name}': {e}")

        # Всегда сбрасываем имя в ноде после попытки удаления
        if self.target_object_name: # Проверяем, есть ли что сбрасывать
             self.target_object_name = ""


    def sv_free(self):
        """Called when the node is removed."""
        self.clear_object()

    # --- Processing ---
    def process(self):
        """Node's core logic: Convert CQ object to Blender mesh."""
        input_socket = self.inputs["Object In"]

        if not input_socket.is_linked:
            self.clear_object()
            return

        try:
            cq_input = input_socket.sv_get()
        except Exception as e:
            self.clear_object()
            raise SocketConnectionError(self, f"No data on input: {e}")

        if cq_input is None:
            self.clear_object()
            return

        # --- Получаем Shape из входа ---
        shape_to_convert = None
        try:
            if isinstance(cq_input, cq.Workplane):
                val = cq_input.val()
                if isinstance(val, cq.Shape):
                    shape_to_convert = val
                elif isinstance(val, list) and val and isinstance(val[0], cq.Shape):
                    shape_to_convert = val[0]
                    logger.warning(f"Viewer received Assembly like object with {len(val)} shapes. Displaying only the first.")
                else:
                    raise ViewerError(self, f"Could not extract a valid Shape from Workplane result (type: {type(val)}). Is the Workplane empty?")
            elif isinstance(cq_input, cq.Shape):
                shape_to_convert = cq_input
            else:
                raise NodeProcessingError(self, f"Unsupported input type: {type(cq_input)}. Expected CadQuery Workplane or Shape.")

            if shape_to_convert is None or not hasattr(shape_to_convert, 'isValid') or not shape_to_convert.isValid():
                 raise ViewerError(self, "Input CadQuery Shape is invalid or empty.")

        except Exception as e: # Ловим ошибки из блока try выше
             self.clear_object() # Очищаем объект, если не смогли получить Shape
             raise e # Передаем ошибку дальше (ViewerError или NodeProcessingError)


        # --- Конвертация в Blender Mesh ---
        mesh_name = f"CQ_{self.id_data.name}_{self.name}_Mesh" # Имя для данных меша
        new_blender_mesh = None # Инициализируем
        try:
            new_blender_mesh = cq_utils.shape_to_blender_mesh(shape_to_convert, mesh_name)
            if new_blender_mesh is None:
                raise ViewerError(self, "Mesh conversion failed (returned None).")
        except Exception as e:
            self.clear_object() # Очищаем при ошибке конвертации
            raise ViewerError(self, f"CadQuery to Blender mesh conversion failed: {e}")

        # --- Обновление/Создание объекта Blender ---
        target_obj = None
        old_mesh_to_remove = None # Меш для удаления после всех операций

        # Пытаемся найти существующий объект по имени ИЗ СВОЙСТВА НОДЫ
        if self.target_object_name and self.target_object_name in bpy.data.objects:
            existing_obj = bpy.data.objects[self.target_object_name]
            logger.debug(f"Found existing object: {self.target_object_name}")
            target_obj = existing_obj
            old_mesh_to_remove = target_obj.data # Запоминаем старый меш для удаления
            # Присваиваем НОВЫЕ данные меша объекту
            target_obj.data = new_blender_mesh
            logger.debug(f"Assigned new mesh data '{new_blender_mesh.name}' to existing object '{target_obj.name}'")

        else:
            # Объект не найден или имя не установлено - создаем новый
            current_target_name = self.target_object_name
            if not current_target_name or current_target_name not in bpy.data.objects:
                base_name = f"CQ_{self.id_data.name}_{self.name}"
                current_target_name = base_name
                count = 1
                while current_target_name in bpy.data.objects:
                    current_target_name = f"{base_name}.{count:03d}"
                    count += 1
                self.target_object_name = current_target_name # Сохраняем новое имя в свойстве ноды
            else:
                logger.debug(f"Reusing target name: {self.target_object_name}")

            logger.debug(f"Creating new Blender object: {self.target_object_name}")
            try:
                target_obj = bpy.data.objects.new(self.target_object_name, new_blender_mesh)
                bpy.context.collection.objects.link(target_obj)
            except Exception as e:
                if new_blender_mesh and new_blender_mesh.users == 0:
                    bpy.data.meshes.remove(new_blender_mesh)
                raise ViewerError(self, f"Failed to create Blender object '{self.target_object_name}': {e}")

        # --- Очистка старого меша ---
        if old_mesh_to_remove and old_mesh_to_remove != new_blender_mesh and old_mesh_to_remove.users == 0:
            logger.debug(f"Removing unused old mesh: '{old_mesh_to_remove.name}'")
            try:
                bpy.data.meshes.remove(old_mesh_to_remove, do_unlink=True)
            except ReferenceError:
                logger.warning(f"Old mesh '{old_mesh_to_remove.name}' seems to be already removed.")
            except Exception as e_rem:
                logger.error(f"Failed to remove old mesh '{old_mesh_to_remove.name}': {e_rem}")

        # Обновляем тег объекта, чтобы Blender перерисовал его
        if target_obj:
            target_obj.update_tag(refresh={'DATA'}) # Обновляем данные

# --- Registration ---
classes = (
    ViewerNode,
)