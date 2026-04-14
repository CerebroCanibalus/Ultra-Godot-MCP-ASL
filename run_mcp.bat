@echo off
REM Ultra Godot MCP v3.1.0 - For the workers and the Iberophones of the world 🏴
REM Plus Ultra: go beyond - MCP server with native TSCN parser

cd /d "%~dp0"

REM Check that Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python 3.10+ from https://python.org
    exit /b 1
)

REM Install the package in editable mode if not installed
python -c "import godot_mcp" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing godot-mcp for the first time...
    pip install -e .
    if errorlevel 1 (
        echo [ERROR] Could not install godot-mcp
        exit /b 1
    )
)

REM Start the MCP server
echo [Ultra Godot MCP v3.1.0] Plus Ultra: Starting server...
echo [Ultra Godot MCP v3.1.0] Native TSCN parser - No Godot required (38 tools), Debug (2 tools)
echo [Ultra Godot MCP v3.1.0] 42 tools available
echo.

python -m godot_mcp.server

if errorlevel 1 (
    echo.
    echo [ERROR] MCP server terminated with errors
    pause
    exit /b 1
)
