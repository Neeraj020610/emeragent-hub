from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class EmergentMCPClientInterface(ABC):
    """
    Abstract interface for Model Context Protocol (MCP) clients connecting to Emergent AI.
    NOTE: As per project guidelines, MCP protocol handles tool and resource execution,
    and MUST NOT be assumed to provide credit balance endpoints.
    """

    @abstractmethod
    def ping(self) -> bool:
        """Check if MCP server connection is responsive."""
        pass

    @abstractmethod
    def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools exposed via MCP."""
        pass

    @abstractmethod
    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool through the MCP protocol."""
        pass


class EmergentMCPClient(EmergentMCPClientInterface):
    def __init__(self, server_url: Optional[str] = None):
        self.server_url = server_url
        self.connected = False

    def ping(self) -> bool:
        return self.connected

    def list_tools(self) -> List[Dict[str, Any]]:
        # Returns standard MCP tool declaration schema
        return [
            {
                "name": "build_project",
                "description": "Trigger code generation or build pipeline on Emergent AI",
                "parameters": {"type": "object", "properties": {"prompt": {"type": "string"}}},
            }
        ]

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if not self.connected:
            return {
                "success": False,
                "error": "Emergent MCP server is not currently connected. Connection must be established first.",
            }
        return {"success": True, "result": "Execution initiated."}
