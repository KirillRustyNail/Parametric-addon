# cadquery_parametric_addon/core/cad_manager.py
import logging
from ..dependencies import cq, cadquery_available # Используем импорт из dependencies
from .exceptions import CadQueryExecutionError, DependencyError, NodeProcessingError

logger = logging.getLogger(__name__)

class CadManager:
    """Handles execution of CadQuery operations."""

    def __init__(self):
        if not cadquery_available:
            logger.error("CadQuery library is not available. Cannot initialize CadManager.")

    def _check_cq(self):
        """Checks if CadQuery is available before execution."""
        if not cadquery_available:
            raise DependencyError("CadQuery library is not installed or failed to import.")

    def create_workplane(self, plane="XY"):
        """Creates a new CadQuery Workplane."""
        self._check_cq()
        try:
            # logger.debug(f"Creating Workplane on plane '{plane}'")
            return cq.Workplane(plane)
        except Exception as e:
            logger.error(f"Failed to create Workplane: {e}", exc_info=True)
            raise CadQueryExecutionError(None, f"Failed to create Workplane: {e}")

    def execute_primitive(self, primitive_name: str, *args, **kwargs):
        """Executes a primitive creation function (like cq.Workplane(...).box).
           Ensures the result is a Workplane.
        """
        self._check_cq()
        # logger.debug(f"Executing primitive: {primitive_name} with args: {args}, kwargs: {kwargs}")
        try:
            wp = cq.Workplane("XY")
            primitive_func = getattr(wp, primitive_name)
            result = primitive_func(*args, **kwargs)

            # --- Проверка и Оборачивание Результата ---
            if isinstance(result, cq.Workplane):
                # Проверяем валидность содержимого Workplane
                if not result.vals() or not result.vals()[0].isValid():
                    logger.warning(f"Primitive '{primitive_name}' resulted in an empty or invalid Workplane.")
                    # Можно вернуть пустой Workplane или вызвать ошибку? Вернем пустой.
                    return cq.Workplane("XY")
                return result # Уже Workplane, возвращаем как есть
            else:
                # Попытка извлечь Shape и обернуть
                shape_val = None
                if hasattr(result, 'val') and callable(result.val):
                    try:
                        val_res = result.val()
                        if isinstance(val_res, cq.Shape) and val_res.isValid():
                            shape_val = val_res
                        elif isinstance(val_res, list) and val_res and isinstance(val_res[0], cq.Shape) and val_res[0].isValid():
                            shape_val = val_res[0]
                            if len(val_res) > 1: logger.warning(f"Primitive '{primitive_name}' returned multiple shapes, wrapping the first one.")
                    except: pass # Игнорируем ошибки извлечения

                if shape_val:
                    logger.debug(f"Primitive '{primitive_name}' returned {type(result)}, wrapping valid Shape in Workplane.")
                    return cq.Workplane("XY").add(shape_val) # Оборачиваем валидный Shape
                else:
                    # Если не Workplane и не содержит валидный Shape, это ошибка
                    logger.error(f"Primitive '{primitive_name}' did not return a valid Workplane or contain a valid Shape (returned {type(result)}).")
                    raise TypeError(f"Primitive '{primitive_name}' did not produce a valid result.")
            # ------------------------------------------
        except AttributeError:
            logger.error(f"CadQuery Workplane has no primitive named '{primitive_name}'")
            raise CadQueryExecutionError(None, f"Unknown primitive '{primitive_name}'")
        except Exception as e:
            logger.error(f"Error executing CadQuery primitive '{primitive_name}': {e}", exc_info=True)
            raise CadQueryExecutionError(None, f"Error in '{primitive_name}': {e}")

    def execute_operation(self, base_obj, other_obj, operation_name: str):
        """Executes a boolean operation (union, cut, intersect) on Workplanes."""
        self._check_cq()
        # logger.debug(f"Executing operation: {operation_name} on {type(base_obj)} with {type(other_obj)}")

        # --- Проверка базового объекта ---
        if not isinstance(base_obj, cq.Workplane):
            logger.error(f"Base object for boolean operation '{operation_name}' must be a Workplane, got {type(base_obj)}")
            # Попытка обернуть Shape? Нет, вызывающий код должен передавать Workplane.
            raise TypeError(f"Base object for '{operation_name}' must be Workplane, got {type(base_obj)}")
        if not base_obj.vals() or not base_obj.vals()[0].isValid():
             raise CadQueryExecutionError(None, f"Base Workplane for '{operation_name}' is empty or invalid.")
        # --------------------------------

        # --- Проверка второго объекта ---
        if not isinstance(other_obj, (cq.Workplane, cq.Shape)):
            raise TypeError(f"'Other' object for '{operation_name}' must be Workplane or Shape, got {type(other_obj)}")
        # Проверяем валидность второго объекта, если он Workplane
        if isinstance(other_obj, cq.Workplane) and (not other_obj.vals() or not other_obj.vals()[0].isValid()):
             raise CadQueryExecutionError(None, f"'Other' Workplane for '{operation_name}' is empty or invalid.")
        # Проверяем валидность второго объекта, если он Shape
        if isinstance(other_obj, cq.Shape) and not other_obj.isValid():
             raise CadQueryExecutionError(None, f"'Other' Shape for '{operation_name}' is invalid.")
        # --------------------------------

        # --- Выполняем операцию на базовом объекте (Workplane) ---
        try:
            # logger.debug(f"  Attempting base_obj.{operation_name}(other_obj)")
            operation_func = getattr(base_obj, operation_name) # Ищем метод у base_obj (Workplane)
            result = operation_func(other_obj) # Передаем второй объект как есть

            # --- Проверка и Оборачивание Результата ---
            if isinstance(result, cq.Workplane):
                if not result.vals() or not result.vals()[0].isValid():
                    logger.warning(f"Operation '{operation_name}' resulted in an empty or invalid Workplane.")
                    # Возвращаем пустой Workplane? Или ошибку? Ошибку надежнее.
                    raise CadQueryExecutionError(None, f"Operation '{operation_name}' result is invalid.")
                return result # Уже валидный Workplane
            else:
                 # Попытка извлечь Shape и обернуть
                 shape_val = None
                 if hasattr(result, 'val') and callable(result.val):
                     try:
                          val_res = result.val();
                          if isinstance(val_res, cq.Shape) and val_res.isValid(): shape_val = val_res
                          elif isinstance(val_res, list) and val_res and isinstance(val_res[0], cq.Shape) and val_res[0].isValid(): shape_val = val_res[0]; # Warning?
                     except: pass
                 if shape_val:
                      logger.debug(f"Operation '{operation_name}' returned {type(result)}, wrapping valid Shape in Workplane.")
                      return cq.Workplane("XY").add(shape_val)
                 else:
                      logger.error(f"Operation '{operation_name}' did not return a valid Workplane or contain a valid Shape (returned {type(result)}).")
                      raise TypeError(f"Operation '{operation_name}' produced an invalid result type.")
            # ------------------------------------------

        except AttributeError:
            logger.error(f"CadQuery Workplane object has no operation named '{operation_name}'")
            raise CadQueryExecutionError(None, f"Workplane operation '{operation_name}' not found.")
        except Exception as e:
            # Ловим возможные ошибки ядра OpenCascade/CadQuery
            logger.error(f"Error executing CadQuery Workplane operation '{operation_name}': {e}", exc_info=True)
            raise CadQueryExecutionError(None, f"Error in '{operation_name}': {e}")

# Глобальный экземпляр менеджера
cad_manager = CadManager()