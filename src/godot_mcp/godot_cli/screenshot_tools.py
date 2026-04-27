"""
Screenshot Tools - Herramientas para capturar frames de escenas.

Usa Godot CLI --write-movie para capturar frames PNG.
NOTA: No es screenshot instantáneo del editor, es captura de escena ejecutándose.
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Optional, Tuple

from .base import GodotCLIWrapper

logger = logging.getLogger(__name__)


# ==================== TOOLS ====================


def capture_scene_frame(
    project_path: str,
    scene_path: str,
    frame_number: int = 1,
    output_path: Optional[str] = None,
    resolution: Optional[Tuple[int, int]] = None,
    godot_path: Optional[str] = None,
    timeout: int = 60,
) -> dict[str, Any]:
    """
    Capture a specific frame from a running scene.

    Executes the scene and captures the specified frame as PNG.
    Uses --write-movie internally.

    Args:
        project_path: Absolute path to the Godot project.
        scene_path: Path to the scene to run.
        frame_number: Which frame to capture (1-based).
        output_path: Where to save the PNG. If None, uses temp directory.
        resolution: Optional (width, height) for the capture.
        godot_path: Optional path to Godot executable.
        timeout: Maximum seconds to wait.

    Returns:
        Dict with success, image_path, resolution, frame_captured.

    Example:
        capture_scene_frame(
            project_path="D:/MyGame",
            scene_path="res://scenes/Main.tscn",
            frame_number=30,  # Capture frame 30 (0.5s at 60fps)
            output_path="D:/tmp/screenshot.png"
        )
    """
    cli = GodotCLIWrapper(godot_path)
    
    is_valid, error = cli.validate_project(project_path)
    if not is_valid:
        return {"success": False, "error": error}
    
    # Setup output directory
    if output_path:
        output_dir = os.path.dirname(output_path)
        output_name = os.path.splitext(os.path.basename(output_path))[0]
    else:
        output_dir = tempfile.gettempdir()
        output_name = f"frame_capture_{os.getpid()}"
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Calculate FPS and quit frame
    fps = 60
    quit_frame = frame_number + 5  # Run a few extra frames to ensure capture
    
    # Build movie writer path
    movie_path = os.path.join(output_dir, output_name)
    
    # Build command
    args = [
        "--headless",
        "--write-movie", movie_path,
        "--quit-after", str(quit_frame),
    ]
    
    if resolution:
        args.extend(["--resolution", f"{resolution[0]}x{resolution[1]}"])
    
    args.append(scene_path)
    
    result = cli.run_command(args, project_path=project_path, timeout=timeout)
    
    # Find the captured frame
    # Godot writes frames as: frame_0001.png, frame_0002.png, etc.
    frame_file = os.path.join(output_dir, f"{output_name}_{frame_number:04d}.png")
    
    # Alternative naming: frame_0001.png in the movie_path directory
    alt_frame_file = os.path.join(output_dir, f"frame_{frame_number:04d}.png")
    
    actual_file = None
    if os.path.isfile(frame_file):
        actual_file = frame_file
    elif os.path.isfile(alt_frame_file):
        actual_file = alt_frame_file
    else:
        # Search for any frame file
        for f in os.listdir(output_dir):
            if f.startswith("frame_") and f.endswith(".png"):
                actual_file = os.path.join(output_dir, f)
                break
    
    cli.cleanup()
    
    if actual_file and os.path.isfile(actual_file):
        # Get image dimensions
        try:
            from PIL import Image
            with Image.open(actual_file) as img:
                width, height = img.size
        except ImportError:
            width, height = None, None
        
        return {
            "success": True,
            "image_path": actual_file,
            "resolution": [width, height] if width else None,
            "frame_captured": frame_number,
            "scene_path": scene_path,
            "errors": result.get("errors", []),
            "warnings": result.get("warnings", []),
        }
    
    return {
        "success": False,
        "error": "Frame capture failed or file not found",
        "searched_paths": [frame_file, alt_frame_file],
        "output_dir": output_dir,
        "godot_output": result.get("prints", []),
        "errors": result.get("errors", []),
    }


def capture_scene_sequence(
    project_path: str,
    scene_path: str,
    frame_count: int = 30,
    output_dir: Optional[str] = None,
    fps: int = 60,
    resolution: Optional[Tuple[int, int]] = None,
    godot_path: Optional[str] = None,
    timeout: int = 120,
) -> dict[str, Any]:
    """
    Capture a sequence of frames from a running scene.

    Args:
        project_path: Absolute path to the Godot project.
        scene_path: Path to the scene to run.
        frame_count: Number of frames to capture.
        output_dir: Directory to save frames. If None, uses temp directory.
        fps: Frames per second.
        resolution: Optional (width, height).
        godot_path: Optional path to Godot executable.
        timeout: Maximum seconds to wait.

    Returns:
        Dict with success, frame_paths, frame_count, duration_seconds.

    Example:
        capture_scene_sequence(
            project_path="D:/MyGame",
            scene_path="res://scenes/Main.tscn",
            frame_count=60,
            output_dir="D:/tmp/frames",
            fps=30
        )
    """
    cli = GodotCLIWrapper(godot_path)
    
    is_valid, error = cli.validate_project(project_path)
    if not is_valid:
        return {"success": False, "error": error}
    
    # Setup output directory
    if not output_dir:
        output_dir = os.path.join(tempfile.gettempdir(), f"sequence_{os.getpid()}")
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Calculate quit frame
    quit_frame = frame_count + 5
    
    # Build movie writer path
    movie_path = os.path.join(output_dir, "frame")
    
    # Build command
    args = [
        "--headless",
        "--write-movie", movie_path,
        "--quit-after", str(quit_frame),
    ]
    
    if resolution:
        args.extend(["--resolution", f"{resolution[0]}x{resolution[1]}"])
    
    args.append(scene_path)
    
    result = cli.run_command(args, project_path=project_path, timeout=timeout)
    
    # Find captured frames
    frame_files = []
    for f in sorted(os.listdir(output_dir)):
        if f.startswith("frame_") and f.endswith(".png"):
            frame_files.append(os.path.join(output_dir, f))
    
    cli.cleanup()
    
    if frame_files:
        return {
            "success": True,
            "frame_paths": frame_files,
            "frame_count": len(frame_files),
            "requested_frames": frame_count,
            "duration_seconds": len(frame_files) / fps,
            "fps": fps,
            "output_dir": output_dir,
            "errors": result.get("errors", []),
            "warnings": result.get("warnings", []),
        }
    
    return {
        "success": False,
        "error": "No frames captured",
        "output_dir": output_dir,
        "godot_output": result.get("prints", []),
        "errors": result.get("errors", []),
    }


# ==================== REGISTRATION ====================


def register_screenshot_tools(mcp) -> None:
    """Register all screenshot tools."""
    logger.info("Registrando screenshot tools...")
    
    mcp.add_tool(capture_scene_frame)
    mcp.add_tool(capture_scene_sequence)
    
    logger.info("[OK] 2 screenshot tools registradas")
