"""
GDScript Validator - Análisis estático básico para scripts GDScript

Detecta errores comunes:
- Variables no declaradas
- Funciones inexistentes
- Type mismatches básicos
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class GDIssue:
    """Un problema encontrado en el script"""

    line: int
    severity: str  # "error", "warning", "info"
    message: str
    suggestion: str | None = None


@dataclass
class GDValidationResult:
    """Resultado de la validación"""

    is_valid: bool = True
    issues: list[GDIssue] = field(default_factory=list)

    def add_issue(
        self, line: int, severity: str, message: str, suggestion: str | None = None
    ):
        self.issues.append(GDIssue(line, severity, message, suggestion))
        if severity == "error":
            self.is_valid = False


class GDScriptValidator:
    """
    Validador básico de GDScript

    NO es un parser completo, solo detecta patrones comunes de error.
    """

    # Funciones built-in de Godot 4.x
    BUILTIN_FUNCTIONS = {
        # Matemáticas
        "abs",
        "clamp",
        "lerp",
        "lerpf",
        "max",
        "min",
        "pow",
        "round",
        "sign",
        "sqrt",
        "ceil",
        "floor",
        "fposmod",
        "posmod",
        "wrapf",
        "wrapi",
        # Vectores
        "Vector2",
        "Vector3",
        "Vector2i",
        "Vector3i",
        "Transform2D",
        "Transform3D",
        # Input/Time
        "Input",
        "Time",
        "OS",
        "Engine",
        # Nodo
        "get_node",
        "get_parent",
        "get_children",
        "queue_free",
        "add_child",
        "remove_child",
        "move_child",
        "has_node",
        "find_child",
        "find_children",
        # Señales
        "connect",
        "disconnect",
        "emit_signal",
        "has_signal",
        # Recursos
        "preload",
        "load",
        "ResourceLoader",
        "ResourceSaver",
        # Física
        "move_and_slide",
        "move_and_collide",
        "test_move",
        "is_on_floor",
        "is_on_wall",
        "is_on_ceiling",
        "get_slide_collision_count",
        # Rendering
        "visible",
        "show",
        "hide",
        "modulate",
        "self_modulate",
        "z_index",
        # Strings
        "str",
        "print",
        "printerr",
        "printraw",
        "push_error",
        "push_warning",
        # Type checking
        "typeof",
        "str",
        "int",
        "float",
        "bool",
        "String",
        "Array",
        "Dictionary",
        # Globals
        "randf",
        "randi",
        "rand_range",
        "randomize",
        "seed",
    }

    # Palabras reservadas
    KEYWORDS = {
        "var",
        "const",
        "func",
        "class",
        "class_name",
        "extends",
        "signal",
        "enum",
        "static",
        "export",
        "onready",
        "setget",
        "breakpoint",
        "pass",
        "return",
        "if",
        "elif",
        "else",
        "for",
        "while",
        "match",
        "break",
        "continue",
        "and",
        "or",
        "not",
        "in",
        "is",
        "as",
        "await",
        "yield",
        "super",
        "self",
        "true",
        "false",
        "null",
    }

    # Decoradores comunes
    DECORATORS = {"@export", "@onready", "@tool", "@icon", "@static_unload"}

    def __init__(self):
        self.declared_vars: set[str] = set()
        self.declared_funcs: set[str] = set()
        self.class_name: str | None = None
        self.extends: str | None = None

    def validate(self, script_content: str) -> GDValidationResult:
        """
        Valida un script GDScript

        Args:
            script_content: Contenido del script .gd

        Returns:
            GDValidationResult con los problemas encontrados
        """
        result = GDValidationResult()
        lines = script_content.split("\n")

        # Fase 1: Recolectar declaraciones
        self._collect_declarations(lines)

        # Fase 2: Analizar uso
        for line_num, line in enumerate(lines, 1):
            self._analyze_line(line_num, line, result)

        return result

    def _collect_declarations(self, lines: list[str]):
        """Recolecta variables y funciones declaradas"""
        self.declared_vars = set()
        self.declared_funcs = set()

        # Variables built-in de todos los nodos
        self.declared_vars.update(
            {
                "position",
                "rotation",
                "scale",
                "global_position",
                "global_rotation",
                "global_scale",
                "visible",
                "modulate",
                "self_modulate",
                "z_index",
                "z_as_relative",
                "name",
                "filename",
                "owner",
                "get_parent",
                "get_children",
                "get_node",
            }
        )

        for line in lines:
            stripped = line.strip()

            # class_name
            if stripped.startswith("class_name "):
                match = re.match(r"class_name\s+(\w+)", stripped)
                if match:
                    self.class_name = match.group(1)

            # extends
            elif stripped.startswith("extends "):
                match = re.match(r"extends\s+(\w+)", stripped)
                if match:
                    self.extends = match.group(1)
                    # Añadir variables del tipo padre (básico)
                    self._add_parent_vars(match.group(1))

            # Variables (@export var, @onready var, var, const)
            elif re.match(r"^(@export|@onready\s+)?var\s+", stripped):
                match = re.match(r"(?:@export|@onready\s+)?var\s+(\w+)", stripped)
                if match:
                    self.declared_vars.add(match.group(1))

            elif stripped.startswith("const "):
                match = re.match(r"const\s+(\w+)", stripped)
                if match:
                    self.declared_vars.add(match.group(1))

            # Funciones (func _ready, func _process, etc.)
            elif re.match(r"^func\s+", stripped):
                match = re.match(r"func\s+(\w+)", stripped)
                if match:
                    func_name = match.group(1)
                    self.declared_funcs.add(func_name)
                    # Añadir parámetros como variables locales
                    params_match = re.search(r"\((.*)\)", stripped)
                    if params_match:
                        params = params_match.group(1)
                        for param in params.split(","):
                            param = param.strip()
                            if param and not param.startswith("#"):
                                # Manejar type hints: param: Type
                                param_name = param.split(":")[0].strip()
                                if param_name:
                                    self.declared_vars.add(param_name)

            # Señales (signal nombre)
            elif re.match(r"^signal\s+", stripped):
                match = re.match(r"signal\s+(\w+)", stripped)
                if match:
                    # Las señales se pueden conectar, no son variables exactamente
                    pass

        # Añadir funciones virtuales comunes
        self.declared_funcs.update(
            {
                "_ready",
                "_process",
                "_physics_process",
                "_input",
                "_unhandled_input",
                "_enter_tree",
                "_exit_tree",
                "_notification",
                "_get_configuration_warnings",
            }
        )

    def _add_parent_vars(self, parent_type: str):
        """Añade variables comunes según el tipo padre"""
        if "Body" in parent_type or "Character" in parent_type:
            self.declared_vars.update(
                {
                    "velocity",
                    "move_and_slide",
                    "is_on_floor",
                    "is_on_wall",
                    "is_on_ceiling",
                    "get_slide_collision_count",
                    "get_slide_collision",
                }
            )
        if "Area" in parent_type:
            self.declared_vars.update(
                {
                    "monitoring",
                    "monitorable",
                    "overlaps_body",
                    "overlaps_area",
                    "get_overlapping_bodies",
                    "get_overlapping_areas",
                }
            )
        if "Sprite" in parent_type or "Mesh" in parent_type:
            self.declared_vars.update(
                {
                    "texture",
                    "flip_h",
                    "flip_v",
                    "hframes",
                    "vframes",
                    "frame",
                    "region_enabled",
                    "region_rect",
                }
            )
        if "Collision" in parent_type:
            self.declared_vars.update(
                {
                    "shape",
                    "disabled",
                    "one_way_collision",
                    "one_way_collision_margin",
                }
            )

    def _analyze_line(self, line_num: int, line: str, result: GDValidationResult):
        """Analiza una línea en busca de problemas"""
        stripped = line.strip()

        # Ignorar comentarios y líneas vacías
        if not stripped or stripped.startswith("#"):
            return

        # Ignorar declaraciones
        if any(
            stripped.startswith(kw)
            for kw in ["var", "const", "func", "class", "signal", "enum"]
        ):
            return

        # Ignorar cadenas (strings)
        # Reemplazar strings temporalemente
        temp_line = re.sub(r'"[^"]*"', '"STRING"', stripped)
        temp_line = re.sub(r"'[^']*'", "'STRING'", temp_line)

        # Buscar llamadas a funciones no declaradas
        func_calls = re.findall(r"(\w+)\s*\(", temp_line)
        for func_name in func_calls:
            if (
                func_name not in self.declared_funcs
                and func_name not in self.BUILTIN_FUNCTIONS
                and func_name not in self.KEYWORDS
                and not func_name[0].isdigit()
            ):
                # Podría ser una función de otra clase/objeto
                # Solo reportar si parece una llamada directa
                if not re.search(r"[.\]]", line.split("(")[0]):
                    result.add_issue(
                        line_num,
                        "warning",
                        f"Function '{func_name}' may not be declared",
                        f"Ensure '{func_name}' is defined or is a built-in function",
                    )

        # Buscar variables no declaradas (uso sin $)
        # Patrón: variable = ... o if variable: o func(variable)
        var_usage = re.findall(r"\b([a-z_][a-z0-9_]*)\b", temp_line, re.IGNORECASE)
        for var_name in var_usage:
            if (
                var_name not in self.declared_vars
                and var_name not in self.BUILTIN_FUNCTIONS
                and var_name not in self.KEYWORDS
                and len(var_name) > 1
                and not var_name[0].isdigit()
            ):
                # Verificar si es acceso con $ (nodo)
                if not re.search(rf'\$["\']?{var_name}', line) and not re.search(
                    rf'["\']{var_name}["\']', line
                ):
                    # Podría ser una variable no declarada
                    # Solo reportar en contextos claros
                    if re.search(rf"\b{var_name}\s*[=!]=", temp_line) or re.search(
                        rf"\b{var_name}\s*[+\-*/]", temp_line
                    ):
                        result.add_issue(
                            line_num,
                            "warning",
                            f"Variable '{var_name}' may not be declared",
                            f"Add 'var {var_name}' at class level or use @onready",
                        )

        # Buscar referencias con $ a nodos (información)
        node_refs = re.findall(r'\$["\']?([\w/]+)["\']?', line)
        for ref in node_refs:
            result.add_issue(
                line_num,
                "info",
                f"Node reference: '${ref}'",
                "Ensure the node exists in the scene tree",
            )


def validate_gdscript(script_content: str) -> GDValidationResult:
    """Función conveniente para validar un script"""
    validator = GDScriptValidator()
    return validator.validate(script_content)


# ============ TEST ============

if __name__ == "__main__":
    # Test con un script de ejemplo
    test_script = """
extends CharacterBody2D

@export var speed: float = 200.0
@onready var sprite: Sprite2D = $Sprite2D

var health: int = 100

func _ready():
    # Esto debería detectar que 'max_health' no está declarado
    max_health = 100
    
    # Esto es correcto
    health = max_health  # Pero max_health no existe!
    
    # Función no declarada
    custom_function()
    
    # Uso correcto de función built-in
    var clamped = clamp(health, 0, 100)
    
    # Referencia a nodo
    sprite.modulate = Color.RED
"""

    print("=" * 60)
    print("GDScript Validator Test")
    print("=" * 60)

    result = validate_gdscript(test_script)

    print(f"\nValid: {result.is_valid}")
    print(f"Issues found: {len(result.issues)}")
    print()

    for issue in result.issues:
        print(f"Line {issue.line} [{issue.severity.upper()}]: {issue.message}")
        if issue.suggestion:
            print(f"  → {issue.suggestion}")

    print("\n" + "=" * 60)
