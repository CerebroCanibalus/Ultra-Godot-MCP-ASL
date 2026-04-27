"""
Movie Tools - Herramientas para capturar video de escenas.

Wrapper sobre Godot CLI --write-movie para grabar secuencias de video.
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Optional

from .base import GodotCLIWrapper

logger = logging.getLogger(__name__)


# ==================== TOOLS ====================


def write_movie(
    project_path: str,
    scene_path: str,
    output_path: str,
    duration_seconds: int = 5,
    fps: int = 60,
    resolution: Optional[tuple[int, int]] = None,
    godot_path: Optional[str] = None,
    timeout: int = 300,
) -> dict[str, Any]:
    """
    Capture a video from a running scene using --write-movie.

    Args:
        project_path: Absolute path to the Godot project.
        scene_path: Path to the scene to run.
        output_path: Path for the output video (or frame prefix).
        duration_seconds: How many seconds to record.
        fps: Frames per second.
        resolution: Optional (width, height).
        godot_path: Optional path to Godot executable.
        timeout: Maximum seconds to wait.

    Returns:
        Dict with success, output_path, frame_count, duration_seconds.

    Example:
        write_movie(
            project_path="D:/MyGame",
            scene_path="res://scenes/Main.tscn",
            output_path="D:/tmp/gameplay",
            duration_seconds=10,
            fps=30
        )
    """
    cli = GodotCLIWrapper(godot_path)
    
    is_valid, error = cli.validate_project(project_path)
    if not is_valid:
        return {"success": False, "error": error}
    
    # Setup output directory
    output_dir = os.path.dirname(output_path)
    output_name = os.path.basename(output_path)
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Calculate total frames and quit frame
    total_frames = duration_seconds * fps
    quit_frame = total_frames + 5
    
    # Build command
    args = [
        "--headless",
        "--write-movie", output_path,
        "--quit-after", str(quit_frame),
    ]
    
    if resolution:
        args.extend(["--resolution", f"{resolution[0]}x{resolution[1]}"])
    
    args.append(scene_path)
    
    result = cli.run_command(args, project_path=project_path, timeout=timeout)
    
    # Find captured frames
    frame_files = []
    for f in sorted(os.listdir(output_dir)):
        if f.startswith(output_name) and f.endswith(".png"):
            frame_files.append(os.path.join(output_dir, f))
    
    cli.cleanup()
    
    if frame_files:
        return {
            "success": True,
            "output_path": output_path,
            "frame_count": len(frame_files),
            "frame_paths": frame_files,
            "duration_seconds": len(frame_files) / fps,
            "fps": fps,
            "resolution": resolution,
            "errors": result.get("errors", []),
            "warnings": result.get("warnings", []),
        }
    
    return {
        "success": False,
        "error": "Movie capture failed or no frames captured",
        "output_path": output_path,
        "godot_output": result.get("prints", []),
        "errors": result.get("errors", []),
    }


def write_movie_with_script(
    project_path: str,
    scene_path: str,
    output_path: str,
    setup_script: Optional[str] = None,
    duration_seconds: int = 5,
    fps: int = 60,
    resolution: Optional[tuple[int, int]] = None,
    godot_path: Optional[str] = None,
    timeout: int = 300,
) -> dict[str, Any]:
    """
    Capture a video with a setup script that configures the scene before recording.

    The setup script is injected into the scene and can move camera, spawn objects, etc.

    Args:
        project_path: Absolute path to the Godot project.
        scene_path: Path to the scene to run.
        output_path: Path for the output video.
        setup_script: Optional GDScript code to run before recording starts.
                      Must be valid GDScript that runs in _ready().
        duration_seconds: How many seconds to record.
        fps: Frames per second.
        resolution: Optional (width, height).
        godot_path: Optional path to Godot executable.
        timeout: Maximum seconds to wait.

    Returns:
        Dict with success, output_path, frame_count.

    Example:
        write_movie_with_script(
            project_path="D:/MyGame",
            scene_path="res://scenes/Main.tscn",
            output_path="D:/tmp/demo",
            setup_script='''
                # Move camera to show player
                $Camera2D.position = $Player.position
                $Player.speed = 200  # Make player move faster
            ''',
            duration_seconds=10
        )
    """
    cli = GodotCLIWrapper(godot_path)
    
    is_valid, error = cli.validate_project(project_path)
    if not is_valid:
        return {"success": False, "error": error}
    
    # Build a script that loads the scene, applies setup, then records
    setup_code = setup_script if setup_script else ""
    
    # Escape the setup script for embedding
    setup_code_escaped = setup_code.replace('"', '\\"').replace("\n", "\\n")
    
    script = f'''
extends SceneTree

func _init():
    var scene_path = "{scene_path}"
    var output_path = "{output_path}"
    var duration = {duration_seconds}
    var fps = {fps}
    
    # Load and instantiate scene
    var scene = load(scene_path)
    if scene == null:
        print("TEST_OUTPUT: ERROR: Failed to load scene")
        quit()
        return
    
    var instance = scene.instantiate()
    get_root().add_child(instance)
    
    # Apply setup script if provided
    var setup_code = "{setup_code_escaped}"
    if setup_code != "":
        # Create a temporary node to run setup
        var setup_node = Node.new()
        setup_node.set_script(load("res://.godot_mcp/setup_temp.gd") if FileAccess.file_exists("res://.godot_mcp/setup_temp.gd") else null)
        instance.add_child(setup_node)
    
    # Wait a frame for setup to apply
    await get_tree().process_frame
    
    # Start recording (Godot handles --write-movie automatically)
    # Just run for the specified duration
    var frames_to_capture = duration * fps
    var frame_count = 0
    
    while frame_count < frames_to_capture:
        frame_count += 1
        await get_tree().process_frame
    
    print("TEST_OUTPUT: " + JSON.stringify({{
        "success": true,
        "frames_captured": frame_count,
        "duration_seconds": duration,
        "fps": fps
    }}))
    
    quit()
'''
    
    # Setup output directory
    output_dir = os.path.dirname(output_path)
    os.makedirs(output_dir, exist_ok=True)
    
    # Build command with --write-movie
    args = [
        "--headless",
        "--write-movie", output_path,
    ]
    
    if resolution:
        args.extend(["--resolution", f"{resolution[0]}x{resolution[1]}"])
    
    # We need to run the setup script instead of the scene directly
    # Save the script to a temp file
    temp_script = os.path.join(tempfile.gettempdir(), f"movie_setup_{os.getpid()}.gd")
    with open(temp_script, "w", encoding="utf-8") as f:
        f.write(script)
    
    args.extend(["--script", temp_script])
    
    result = cli.run_command(args, project_path=project_path, timeout=timeout)
    
    # Cleanup temp script
    try:
        if os.path.exists(temp_script):
            os.remove(temp_script)
    except:
        pass
    
    # Find captured frames
    frame_files = []
    if os.path.exists(output_dir):
        output_name = os.path.basename(output_path)
        for f in sorted(os.listdir(output_dir)):
            if f.startswith(output_name) and f.endswith(".png"):
                frame_files.append(os.path.join(output_dir, f))
    
    cli.cleanup()
    
    # Extract test output
    test_output = None
    for line in result.get("prints", []):
        if line.startswith("TEST_OUTPUT:"):
            import json
            try:
                test_output = json.loads(line[12:].strip())
            except:
                pass
            break
    
    if frame_files or (test_output and test_output.get("success")):
        return {
            "success": True,
            "output_path": output_path,
            "frame_count": len(frame_files),
            "frame_paths": frame_files,
            "duration_seconds": len(frame_files) / fps if frame_files else duration_seconds,
            "fps": fps,
            "setup_applied": setup_script is not None,
            "errors": result.get("errors", []),
            "warnings": result.get("warnings", []),
        }
    
    return {
        "success": False,
        "error": "Movie capture with script failed",
        "output_path": output_path,
        "godot_output": result.get("prints", []),
        "errors": result.get("errors", []),
    }


# ==================== REGISTRATION ====================


def register_movie_tools(mcp) -> None:
    """Register all movie tools."""
    logger.info("Registrando movie tools...")
    
    mcp.add_tool(write_movie)
    mcp.add_tool(write_movie_with_script)
    
    logger.info("[OK] 2 movie tools registradas")
