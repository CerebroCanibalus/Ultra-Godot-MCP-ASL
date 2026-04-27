"""Base utilities for Godot CLI operations.

Provides GodotCLIWrapper for unified Godot CLI command execution
with proper error handling, logging, and temporary file management.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# Rutas de búsqueda para ejecutable de Godot
GODOT_SEARCH_PATHS = [
    # Windows - versiones específicas del General
    r"D:\Mis Juegos\Godot",
    # Windows - ubicaciones comunes
    r"C:\Program Files\Godot",
    r"C:\Program Files (x86)\Godot",
    # Linux
    "/usr/local/bin",
    "/usr/bin",
    # macOS
    "/Applications",
]

# Nombres de ejecutables (más reciente primero)
# NOTA: En Windows, preferir la versión _console.exe porque:
# 1. Muestra output en tiempo real (no bufferizado)
# 2. Permite capturar stdout/stderr correctamente
# 3. No requiere --no-window ni hacks de redirección
GODOT_EXECUTABLE_NAMES = [
    "Godot_v4.6.1-stable_win64_console.exe",
    "Godot_v4.6.1-stable_win64.exe",
    "Godot_v4.5.1-stable_win64_console.exe",
    "Godot_v4.5.1-stable_win64.exe",
    "Godot_v4.5-stable_win64_console.exe",
    "Godot_v4.5-stable_win64.exe",
    "godot",  # Linux/macOS
    "Godot",  # macOS
]


def find_godot_executable(godot_path: Optional[str] = None) -> Optional[str]:
    """Find Godot executable in common locations.
    
    Args:
        godot_path: Optional explicit path to Godot executable.
                   If provided and valid, returns it directly.
    
    Returns:
        Absolute path to Godot executable, or None if not found.
    """
    # If explicit path provided, validate and return
    if godot_path:
        if os.path.isfile(godot_path):
            return os.path.abspath(godot_path)
        logger.warning(f"Provided godot_path not found: {godot_path}")
        # Fall through to auto-detection
    
    # First check PATH
    godot_in_path = shutil.which("godot") or shutil.which("Godot")
    if godot_in_path:
        return godot_in_path

    # Search in common paths
    for search_path in GODOT_SEARCH_PATHS:
        if not os.path.exists(search_path):
            continue

        for exe_name in GODOT_EXECUTABLE_NAMES:
            candidate = os.path.join(search_path, exe_name)
            if os.path.isfile(candidate):
                return candidate

    return None


def parse_godot_log(log_content: str) -> Dict[str, List[str]]:
    """Parse Godot log output into categorized messages.
    
    Godot output format:
    - ERROR: ...
    - WARNING: ...
    - USER SCRIPT: ... (prints from print())
    - At: ... (stack trace lines)
    - Other lines (info, debug, etc.)
    
    Returns:
        Dict with keys: errors, warnings, prints, info, stack_traces
    """
    errors = []
    warnings = []
    prints = []
    info = []
    stack_traces = []

    for line in log_content.splitlines():
        line = line.strip()
        if not line:
            continue

        # Error lines
        if line.startswith("ERROR:") or line.startswith("ERROR "):
            errors.append(line)
        elif line.startswith("At:"):
            stack_traces.append(line)
        elif line.startswith("WARNING:") or line.startswith("WARNING "):
            warnings.append(line)
        elif line.startswith("USER SCRIPT:") or line.startswith("   at"):
            prints.append(line)
        elif line.startswith("TEST_OUTPUT:"):
            # Capturar prints personalizados de scripts de prueba
            prints.append(line)
        elif line.startswith("SCRIPT ERROR:"):
            errors.append(line)
        elif line.startswith("   "):
            stack_traces.append(line)
        else:
            info.append(line)

    return {
        "errors": errors,
        "warnings": warnings,
        "prints": prints,
        "info": info,
        "stack_traces": stack_traces,
    }


class GodotCLIWrapper:
    """Wrapper for Godot CLI operations.
    
    Provides a unified interface for running Godot commands
    with proper error handling and logging.
    
    Usage:
        cli = GodotCLIWrapper()
        result = cli.run_command(["--headless", "--check-only"], 
                                project_path="/path/to/project")
        if result["success"]:
            print(result["prints"])
    """

    def __init__(self, godot_path: Optional[str] = None):
        """Initialize wrapper.
        
        Args:
            godot_path: Optional path to Godot executable. 
                       If None, auto-detects.
        """
        self.godot_path = find_godot_executable(godot_path)
        self._temp_files: List[str] = []

    def validate_project(self, project_path: str) -> tuple[bool, Optional[str]]:
        """Validate that path is a valid Godot project.
        
        Returns:
            (is_valid, error_message)
        """
        project_path = os.path.abspath(project_path)
        if not os.path.isdir(project_path):
            return False, f"Project path not found: {project_path}"

        project_godot = os.path.join(project_path, "project.godot")
        if not os.path.isfile(project_godot):
            return False, f"Not a valid Godot project (no project.godot): {project_path}"

        return True, None

    def run_command(
        self,
        args: List[str],
        project_path: Optional[str] = None,
        timeout: int = 30,
        capture_log: bool = True,
    ) -> Dict[str, Any]:
        """Run a Godot CLI command with proper setup.
        
        Args:
            args: Command arguments (without 'godot' executable)
            project_path: Optional project path to add --path
            timeout: Maximum seconds to wait
            capture_log: Whether to capture log file
            
        Returns:
            Dict with success, exit_code, errors, warnings, prints, info, stack_traces
        """
        if not self.godot_path:
            return {
                "success": False,
                "error": "Godot executable not found. "
                        "Provide godot_path or install Godot in a common location.",
                "searched_paths": GODOT_SEARCH_PATHS,
            }

        if not os.path.isfile(self.godot_path):
            return {
                "success": False,
                "error": f"Godot executable not found at: {self.godot_path}",
            }

        # Build command
        cmd = [self.godot_path] + args

        if project_path:
            cmd.extend(["--path", project_path])

        # Create log file
        log_file = None
        if capture_log:
            log_file = os.path.join(
                tempfile.gettempdir(), f"godot_cli_{os.getpid()}_{id(self)}.log"
            )
            self._temp_files.append(log_file)
            cmd.extend(["--log-file", log_file])

        logger.info(f"Running Godot: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
            )

            # Read log file
            log_content = ""
            if log_file and os.path.exists(log_file):
                with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                    log_content = f.read()

            # Combine all output: log file + stdout + stderr
            # stdout captures print() from GDScript scripts
            stdout_content = result.stdout or ""
            stderr_content = result.stderr or ""
            combined_output = log_content + "\n" + stdout_content + "\n" + stderr_content

            # Parse output
            parsed = parse_godot_log(combined_output)

            return {
                "success": result.returncode == 0,
                "exit_code": result.returncode,
                "errors": parsed["errors"],
                "warnings": parsed["warnings"],
                "prints": parsed["prints"],
                "info": parsed["info"],
                "stack_traces": parsed["stack_traces"],
                "godot_path": self.godot_path,
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"Godot timed out after {timeout} seconds",
                "godot_path": self.godot_path,
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to run Godot: {e}",
                "godot_path": self.godot_path,
            }

    def run_script(
        self,
        script_content: str,
        project_path: str,
        timeout: int = 30,
    ) -> Dict[str, Any]:
        """Run GDScript content via --script.
        
        Creates temporary script file and executes it.
        
        Args:
            script_content: GDScript code to execute
            project_path: Project path
            timeout: Maximum seconds
            
        Returns:
            Command result dict
        """
        # Validate project
        is_valid, error = self.validate_project(project_path)
        if not is_valid:
            return {"success": False, "error": error}

        # Create temporary script
        script_file = os.path.join(
            tempfile.gettempdir(), f"godot_script_{os.getpid()}.gd"
        )
        self._temp_files.append(script_file)

        try:
            with open(script_file, "w", encoding="utf-8") as f:
                f.write(script_content)

            args = [
                "--headless",
                "--script",
                script_file,
            ]

            return self.run_command(args, project_path=project_path, timeout=timeout)

        except Exception as e:
            return {"success": False, "error": f"Failed to write script: {e}"}

    def cleanup(self):
        """Remove temporary files created by this wrapper."""
        for file_path in self._temp_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.debug(f"Cleaned up temp file: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to clean up {file_path}: {e}")
        self._temp_files.clear()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup temp files."""
        self.cleanup()
        return False
