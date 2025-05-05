# cadquery_parametric_addon/core/exceptions.py

class CadQueryParametricError(Exception):
    """Base exception for the addon."""
    pass

class NodeProcessingError(CadQueryParametricError):
    """Error during node processing."""
    def __init__(self, node, message=""):
        self.node = node
        self.message = message
        super().__init__(f"Error in node '{node.name}' ({node.bl_idname}): {message}")

class CadQueryExecutionError(NodeProcessingError):
    """Error executing a CadQuery command."""
    pass

class SocketConnectionError(NodeProcessingError):
    """Error related to socket connections or data."""
    pass

class NoDataError(SocketConnectionError):
    """Raised when expected data is missing from a socket."""
    def __init__(self, node, socket):
        super().__init__(node, f"No data available on input socket '{socket.name}'")

class ViewerError(NodeProcessingError):
    """Error specific to the Viewer node."""
    pass

class DependencyError(CadQueryParametricError):
    """Missing dependency error."""
    pass