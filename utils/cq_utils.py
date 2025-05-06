# cadquery_parametric_addon/utils/cq_utils.py
import bpy
import logging
from ..dependencies import cq, cadquery_available

logger = logging.getLogger(__name__)

def shape_to_blender_mesh(shape: cq.Shape, mesh_name: str,
                          tolerance=0.1, angular_tolerance=0.1) -> bpy.types.Mesh | None: # Добавляем параметры
    """Converts a CadQuery Shape to a Blender Mesh using tessellation."""
    if not cadquery_available:
        logger.error("CadQuery library not available for shape conversion.")
        return None
    if not isinstance(shape, cq.Shape):
         logger.error(f"Input is not a CadQuery Shape (type: {type(shape)})")
         return None
    if not shape.isValid():
         logger.warning(f"Input CadQuery Shape is invalid.")
         return None

    try:
        # Используем tessellate для получения вершин и треугольников
        # Настройте точность по необходимости
        vertices, triangles = shape.tessellate(tolerance=tolerance, angularTolerance=angular_tolerance)

        if not vertices or not triangles:
            logger.warning(f"Tessellation resulted in no vertices or triangles for mesh '{mesh_name}'. Shape might be 2D or invalid.")
            return None

        # Создаем новый меш Blender
        mesh = bpy.data.meshes.new(mesh_name)
        # Заполняем меш данными
        mesh.from_pydata(vertices, [], triangles) # Второй аргумент - ребра (edges), пока пустой
        mesh.update(calc_edges=True) # Рассчитываем ребра и нормали
        mesh.validate() # Проверяем меш на корректность
        return mesh

    except Exception as e:
        logger.error(f"Error during shape tessellation or mesh creation for '{mesh_name}': {e}", exc_info=True)
        # Важно: Не удаляем меш здесь, если он был создан, т.к. вызывающий код может это сделать
        return None

# --- Функция update_blender_object удалена отсюда ---