"""
JSON-RPC Client for Godot LSP/DAP protocols.

Godot exposes LSP on port 6005 and DAP on port 6006 when the editor is open.
This client provides a unified interface for both protocols.
"""

from __future__ import annotations

import json
import logging
import socket
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class JSONRPCError(Exception):
    """Exception for JSON-RPC errors."""
    
    def __init__(self, code: int, message: str, data: Any = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(f"JSON-RPC Error {code}: {message}")


class GodotRPCClient:
    """
    Generic JSON-RPC client for Godot protocols (LSP/DAP).
    
    Usage:
        client = GodotRPCClient("localhost", 6005)  # LSP
        client.connect()
        result = client.call("textDocument/completion", {...})
        client.disconnect()
    """
    
    def __init__(self, host: str = "localhost", port: int = 6005, timeout: float = 5.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.socket: Optional[socket.socket] = None
        self._message_id = 0
        self._lock = threading.Lock()
        self._callbacks: Dict[int, Callable] = {}
        self._running = False
        self._reader_thread: Optional[threading.Thread] = None
    
    def connect(self) -> bool:
        """Connect to the Godot protocol server."""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.timeout)
            self.socket.connect((self.host, self.port))
            self._running = True
            
            # Start reader thread
            self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
            self._reader_thread.start()
            
            logger.info(f"Connected to Godot RPC at {self.host}:{self.port}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to {self.host}:{self.port}: {e}")
            self.socket = None
            return False
    
    def disconnect(self) -> None:
        """Disconnect from the server."""
        self._running = False
        
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
        
        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=2.0)
        
        logger.info("Disconnected from Godot RPC")
    
    def is_connected(self) -> bool:
        """Check if connected."""
        return self.socket is not None and self._running
    
    def _get_next_id(self) -> int:
        """Get next message ID."""
        with self._lock:
            self._message_id += 1
            return self._message_id
    
    def _send_message(self, message: dict) -> None:
        """Send a JSON-RPC message."""
        if not self.socket:
            raise ConnectionError("Not connected")
        
        content = json.dumps(message)
        header = f"Content-Length: {len(content)}\r\n\r\n"
        
        with self._lock:
            self.socket.sendall(header.encode("utf-8"))
            self.socket.sendall(content.encode("utf-8"))
    
    def _read_loop(self) -> None:
        """Background thread to read responses."""
        buffer = b""
        
        while self._running and self.socket:
            try:
                data = self.socket.recv(4096)
                if not data:
                    break
                
                buffer += data
                
                # Parse messages
                while True:
                    # Find Content-Length header
                    header_end = buffer.find(b"\r\n\r\n")
                    if header_end == -1:
                        break
                    
                    header = buffer[:header_end].decode("utf-8")
                    content_length = None
                    
                    for line in header.split("\r\n"):
                        if line.startswith("Content-Length:"):
                            content_length = int(line[15:].strip())
                            break
                    
                    if content_length is None:
                        logger.error("Missing Content-Length header")
                        buffer = buffer[header_end + 4:]
                        continue
                    
                    # Check if we have full content
                    total_length = header_end + 4 + content_length
                    if len(buffer) < total_length:
                        break
                    
                    # Extract and parse content
                    content = buffer[header_end + 4:total_length]
                    buffer = buffer[total_length:]
                    
                    try:
                        message = json.loads(content.decode("utf-8"))
                        self._handle_message(message)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse JSON: {e}")
                        
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    logger.error(f"Read error: {e}")
                break
    
    def _handle_message(self, message: dict) -> None:
        """Handle incoming message."""
        if "id" in message:
            msg_id = message["id"]
            callback = self._callbacks.pop(msg_id, None)
            if callback:
                callback(message)
    
    def call(self, method: str, params: dict = None, timeout: float = None) -> dict:
        """
        Make a synchronous JSON-RPC call.
        
        Args:
            method: Method name.
            params: Method parameters.
            timeout: Maximum seconds to wait for response.
        
        Returns:
            Response dict.
        """
        msg_id = self._get_next_id()
        
        message = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "method": method,
        }
        
        if params:
            message["params"] = params
        
        # Setup response handler
        response_container = {}
        event = threading.Event()
        
        def callback(msg):
            response_container["message"] = msg
            event.set()
        
        self._callbacks[msg_id] = callback
        
        # Send and wait
        self._send_message(message)
        
        wait_time = timeout or self.timeout
        if not event.wait(timeout=wait_time):
            self._callbacks.pop(msg_id, None)
            raise TimeoutError(f"RPC call timed out after {wait_time}s")
        
        response = response_container["message"]
        
        if "error" in response:
            error = response["error"]
            raise JSONRPCError(error.get("code", -1), error.get("message", "Unknown error"))
        
        return response.get("result", {})
    
    def notify(self, method: str, params: dict = None) -> None:
        """
        Send a notification (no response expected).
        
        Args:
            method: Method name.
            params: Method parameters.
        """
        message = {
            "jsonrpc": "2.0",
            "method": method,
        }
        
        if params:
            message["params"] = params
        
        self._send_message(message)


class GodotLSPClient(GodotRPCClient):
    """
    Specialized client for Godot Language Server Protocol (port 6005).
    
    Provides convenience methods for common LSP operations.
    """
    
    def __init__(self, host: str = "localhost", port: int = 6005):
        super().__init__(host, port)
        self._initialized = False
    
    def initialize(self, root_path: str) -> dict:
        """Initialize LSP connection."""
        result = self.call("initialize", {
            "processId": None,
            "rootPath": root_path,
            "capabilities": {},
        })
        self._initialized = True
        
        # Send initialized notification
        self.notify("initialized", {})
        
        return result
    
    def get_completions(self, file_path: str, line: int, column: int) -> List[dict]:
        """Get code completions at position."""
        result = self.call("textDocument/completion", {
            "textDocument": {"uri": f"file://{file_path}"},
            "position": {"line": line, "character": column},
        })
        
        return result.get("items", [])
    
    def get_hover(self, file_path: str, line: int, column: int) -> Optional[dict]:
        """Get hover information at position."""
        result = self.call("textDocument/hover", {
            "textDocument": {"uri": f"file://{file_path}"},
            "position": {"line": line, "character": column},
        })
        
        return result if result else None
    
    def get_document_symbols(self, file_path: str) -> List[dict]:
        """Get all symbols in a document."""
        result = self.call("textDocument/documentSymbol", {
            "textDocument": {"uri": f"file://{file_path}"},
        })
        
        return result if result else []
    
    def get_diagnostics(self, file_path: str) -> List[dict]:
        """Get diagnostics (errors/warnings) for a file."""
        # Publish diagnostics is server -> client
        # We need to open the document first
        self.notify("textDocument/didOpen", {
            "textDocument": {
                "uri": f"file://{file_path}",
                "languageId": "gdscript",
                "version": 1,
                "text": "",  # Empty - server will read from disk
            }
        })
        
        # Wait a bit for diagnostics
        time.sleep(0.5)
        
        # For now, return empty - real implementation would track published diagnostics
        return []
    
    def shutdown(self) -> None:
        """Shutdown LSP connection gracefully."""
        if self._initialized:
            try:
                self.call("shutdown", {})
                self.notify("exit", {})
            except:
                pass
            self._initialized = False
        self.disconnect()


class GodotDAPClient(GodotRPCClient):
    """
    Specialized client for Godot Debug Adapter Protocol (port 6006).
    
    Provides convenience methods for debugging operations.
    """
    
    def __init__(self, host: str = "localhost", port: int = 6006):
        super().__init__(host, port)
        self._initialized = False
    
    def initialize(self) -> dict:
        """Initialize DAP connection."""
        result = self.call("initialize", {
            "clientID": "godot-mcp",
            "clientName": "Godot MCP",
            "adapterID": "godot",
            "linesStartAt1": True,
            "columnsStartAt1": True,
            "supportsVariableType": True,
            "supportsVariablePaging": False,
            "supportsRunInTerminalRequest": False,
        })
        self._initialized = True
        return result
    
    def launch(self, project_path: str, scene_path: str = None) -> dict:
        """Launch debugging session."""
        config = {
            "type": "godot",
            "request": "launch",
            "project": project_path,
        }
        
        if scene_path:
            config["scene"] = scene_path
        
        return self.call("launch", config)
    
    def set_breakpoint(self, file_path: str, line: int, condition: str = None) -> dict:
        """Set a breakpoint."""
        breakpoint_spec = {"line": line}
        if condition:
            breakpoint_spec["condition"] = condition
        
        return self.call("setBreakpoints", {
            "source": {"path": file_path},
            "breakpoints": [breakpoint_spec],
        })
    
    def continue_execution(self) -> dict:
        """Continue execution."""
        return self.call("continue", {"threadId": 1})
    
    def step_over(self) -> dict:
        """Step over."""
        return self.call("next", {"threadId": 1})
    
    def step_into(self) -> dict:
        """Step into."""
        return self.call("stepIn", {"threadId": 1})
    
    def step_out(self) -> dict:
        """Step out."""
        return self.call("stepOut", {"threadId": 1})
    
    def get_stack_trace(self) -> List[dict]:
        """Get current stack trace."""
        result = self.call("stackTrace", {"threadId": 1})
        return result.get("stackFrames", [])
    
    def get_scopes(self, frame_id: int) -> List[dict]:
        """Get scopes for a stack frame."""
        result = self.call("scopes", {"frameId": frame_id})
        return result.get("scopes", [])
    
    def get_variables(self, variables_reference: int) -> List[dict]:
        """Get variables in a scope."""
        result = self.call("variables", {"variablesReference": variables_reference})
        return result.get("variables", [])
    
    def disconnect_debugger(self) -> None:
        """Disconnect debugger gracefully."""
        if self._initialized:
            try:
                self.call("disconnect", {"restart": False})
            except:
                pass
            self._initialized = False
        self.disconnect()


# ==================== Utility Functions ====================

def check_lsp_available(host: str = "localhost", port: int = 6005, timeout: float = 2.0) -> bool:
    """Check if Godot LSP is available."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        sock.close()
        return True
    except:
        return False


def check_dap_available(host: str = "localhost", port: int = 6006, timeout: float = 2.0) -> bool:
    """Check if Godot DAP is available."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        sock.close()
        return True
    except:
        return False
