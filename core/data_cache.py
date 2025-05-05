# cadquery_parametric_addon/core/data_cache.py
import logging
from typing import TypeAlias, Any

logger = logging.getLogger(__name__)

# Используем строку для SocketId, чтобы избежать циклического импорта
SocketId: TypeAlias = str
socket_data_cache: dict[SocketId, Any] = {}

# Простая реализация кеша. Для сложных объектов CadQuery может потребоваться
# более умное управление памятью или копирование.
# Пока что избегаем deepcopy для производительности.

def sv_set_socket(socket_id: SocketId, data: Any):
    """Sets data for a socket ID."""
    # logger.debug(f"Setting data for socket {socket_id}: {type(data)}")
    socket_data_cache[socket_id] = data

def sv_get_socket(socket_id: SocketId, node_context=None, socket_context=None) -> Any:
    """Gets data for a socket ID. Raises NoDataError if not found."""
    try:
        data = socket_data_cache[socket_id]
        # logger.debug(f"Getting data for socket {socket_id}: {type(data)}")
        # ВАЖНО: CadQuery объекты изменяемы. Если нода модифицирует
        # входной объект, это повлияет на все последующие ноды.
        # Возможно, потребуется копирование здесь (data.copy() для Workplane?)
        # или передача неизменяемых Shape. Пока оставляем как есть.
        return data
    except KeyError:
        if node_context and socket_context:
             # Импортируем здесь, чтобы избежать циклического импорта
            from .exceptions import NoDataError
            raise NoDataError(node_context, socket_context)
        else:
            # Менее информативная ошибка, если нет контекста
            raise KeyError(f"No data found for socket ID: {socket_id}")


def sv_forget_socket(socket_id: SocketId):
    """Removes data for a socket ID from the cache."""
    if socket_id in socket_data_cache:
        # logger.debug(f"Forgetting data for socket {socket_id}")
        del socket_data_cache[socket_id]

def clear_all_socket_cache():
    """Clears the entire socket data cache."""
    logger.info("Clearing all socket data cache.")
    socket_data_cache.clear()