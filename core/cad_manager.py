# cadquery_parametric_addon/core/cad_manager.py
import logging
from ..dependencies import cq, cadquery_available
from .exceptions import CadQueryExecutionError, DependencyError

logger = logging.getLogger(__name__)

class CadManager:
    """Handles execution of CadQuery operations."""

    def __init__(self):
        if not cadquery_available:
            logger.error("CadQuery library is not available. Cannot initialize CadManager.")
            # Не выбрасываем исключение здесь, чтобы аддон мог загрузиться
            # и показать ошибку в нодах.

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
        """Executes a primitive creation function (like cq.Workplane(...).box)."""
        self._check_cq()
        # logger.debug(f"Executing primitive: {primitive_name} with args: {args}, kwargs: {kwargs}")
        try:
            # Начинаем с базовой плоскости
            wp = cq.Workplane("XY")
            primitive_func = getattr(wp, primitive_name)
            result = primitive_func(*args, **kwargs)
            if not isinstance(result, cq.Workplane):
                 raise TypeError(f"Primitive '{primitive_name}' did not return a Workplane object.")
            # logger.debug(f"Primitive result type: {type(result)}")
            return result
        except AttributeError:
            logger.error(f"CadQuery Workplane has no primitive named '{primitive_name}'")
            raise CadQueryExecutionError(None, f"Unknown primitive '{primitive_name}'")
        except Exception as e:
            logger.error(f"Error executing CadQuery primitive '{primitive_name}': {e}", exc_info=True)
            raise CadQueryExecutionError(None, f"Error in '{primitive_name}': {e}")

    def execute_operation(self, base_obj, other_obj, operation_name: str):
        """Executes a boolean operation (union, cut, intersect)."""
        self._check_cq()
        # logger.debug(f"Executing operation: {operation_name}")

        if not isinstance(base_obj, (cq.Workplane, cq.Shape)):
            raise TypeError(f"Base object for '{operation_name}' must be Workplane or Shape, got {type(base_obj)}")
        if not isinstance(other_obj, (cq.Workplane, cq.Shape)):
             # Попытка получить Shape из Workplane, если нужно
             if isinstance(other_obj, cq.Workplane):
                 try:
                     other_obj_val = other_obj.val() # Получаем Shape
                     if not isinstance(other_obj_val, cq.Shape):
                          raise TypeError("Workplane did not yield a valid Shape")
                     other_obj = other_obj_val
                 except Exception as e:
                     logger.error(f"Could not get Shape from Workplane for operation '{operation_name}': {e}")
                     raise CadQueryExecutionError(None, f"Invalid 'other' object for '{operation_name}': Could not extract Shape.")
             else:
                 raise TypeError(f"'Other' object for '{operation_name}' must be Workplane or Shape, got {type(other_obj)}")


        try:
            operation_func = getattr(base_obj, operation_name)
            # Операции обычно принимают Shape, не Workplane
            # other_shape = other_obj.val() if isinstance(other_obj, cq.Workplane) else other_obj
            result = operation_func(other_obj) # Передаем Shape
            # logger.debug(f"Operation result type: {type(result)}")
            return result
        except AttributeError:
            logger.error(f"CadQuery object has no operation named '{operation_name}'")
            raise CadQueryExecutionError(None, f"Unknown operation '{operation_name}'")
        except Exception as e:
            logger.error(f"Error executing CadQuery operation '{operation_name}': {e}", exc_info=True)
            raise CadQueryExecutionError(None, f"Error in '{operation_name}': {e}")

# Создаем один экземпляр менеджера для использования во всем аддоне
cad_manager = CadManager()