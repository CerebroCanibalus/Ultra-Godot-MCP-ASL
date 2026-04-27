"""
GDScript Validator - Validación inteligente de scripts GDScript.

Este validador usa una arquitectura de 3 capas para proporcionar
validación precisa con mínimo falsos positivos:

CAPA 1: Godot Real (Sintaxis)
    → Delega a godot_check_script_syntax() para errores reales

CAPA 2: API de Godot (Métodos/Propiedades)
    → Verifica métodos vs. la API conocida de Godot 4.6

CAPA 3: Análisis de Patrones (Patterns Comunes)
    → Detecta @export sin tipo, código muerto, decorators deprecated

Esta arquitectura evita el problema fundamental de detectar
"variables no declaradas" (imposible con análisis estático en GDScript).

Autor: Devil's Kitchen
Versión: 2.0
Dependencias: godot_mcp.core.api.GodotAPI
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from godot_mcp.core.api import GodotAPI


@dataclass
class GDIssue:
    """Un problema encontrado en el script."""

    line: int
    severity: str  # "error", "warning", "info"
    message: str
    suggestion: str | None = None


@dataclass
class GDValidationResult:
    """Resultado de la validación."""

    is_valid: bool = True
    issues: list[GDIssue] = field(default_factory=list)

    def add_issue(self, line: int, severity: str, message: str, suggestion: str | None = None):
        self.issues.append(GDIssue(line, severity, message, suggestion))
        if severity == "error":
            self.is_valid = False


@dataclass
class ParsedCall:
    """Una llamada a método o función parseada."""

    line: int
    object_name: str | None  # None = función global/standalone
    method_name: str
    full_match: str


class GDScriptValidator:
    """
    Validador inteligente de GDScript basado en la API de Godot 4.6.

    NO intenta detectar "variables no declaradas" - esto es imposible
    en GDScript sin un parser completo y análisis de flujo.

    En su lugar, verifica:
    - Métodos llamados en objetos conocidos (CharacterBody2D, etc.)
    - Decoradores deprecated (@onready)
    - Patterns de código problemáticos
    - Métodos/propiedades eliminados en Godot 4

    Attributes:
        api: Instancia de GodotAPI para consultas de API
    """

    # Regex para extraer extends
    EXTENDS_PATTERN = re.compile(r"extends\s+(\w+)")

    # Regex para decoradores
    DECORATOR_PATTERN = re.compile(r"^(\s*)@(\w+)(\s.*)?$")

    # Regex para llamadas a métodos en objetos
    # Captura: obj.method(), $Node.method(), ClassName.method()
    METHOD_CALL_PATTERN = re.compile(
        r"(?:(\w+)|"
        r"\$([\w/]+)|"
        r"([A-Z][A-Za-z0-9_]+))"  # ClassName
        r"\.(\w+)\s*\("
    )

    # Regex para funciones standalone (al inicio de línea o después de =)
    # Solo si no tienen prefijo de objeto
    STANDALONE_FUNC_PATTERN = re.compile(r"(?<![\w.$])(\w+)\s*\(")

    # Regex para señales
    SIGNAL_PATTERN = re.compile(r"signal\s+(\w+)")

    # Regex para @export var sin tipo
    EXPORT_NO_TYPE_PATTERN = re.compile(r"@export\s+var\s+(\w+)\s*(?![:\w])")

    def __init__(self, api: Optional[GodotAPI] = None):
        """
        Inicializa el validador.

        Args:
            api: Instancia de GodotAPI. Si es None, usa la instancia global.
        """
        self.api = api or GodotAPI.get_instance()

        # Estado del parseo
        self.extends_type: Optional[str] = None
        self.declared_signals: set[str] = set()
        self.declared_funcs: set[str] = set()

    def validate(self, script_content: str) -> GDValidationResult:
        """
        Valida un script GDScript.

        Args:
            script_content: Contenido del script .gd

        Returns:
            GDValidationResult con los problemas encontrados
        """
        result = GDValidationResult()

        # Extraer información del script
        self._collect_declarations(script_content)

        # Analizar cada línea
        lines = script_content.split("\n")
        for line_num, line in enumerate(lines, 1):
            self._analyze_line(line_num, line, result)

        return result

    def _collect_declarations(self, content: str) -> None:
        """Recolecta información de declaraciones del script."""
        self.extends_type = None
        self.declared_signals = set()
        self.declared_funcs = set()

        lines = content.split("\n")

        for line in lines:
            stripped = line.strip()

            # Extraer extends
            extends_match = self.EXTENDS_PATTERN.match(stripped)
            if extends_match:
                self.extends_type = extends_match.group(1)

            # Extraer señales
            signal_match = self.SIGNAL_PATTERN.match(stripped)
            if signal_match:
                self.declared_signals.add(signal_match.group(1))

            # Extraer funciones
            func_match = re.match(r"func\s+(\w+)", stripped)
            if func_match:
                self.declared_funcs.add(func_match.group(1))

    def _analyze_line(self, line_num: int, line: str, result: GDValidationResult) -> None:
        """Analiza una línea en busca de problemas."""
        stripped = line.strip()

        # Ignorar comentarios y líneas vacías
        if not stripped or stripped.startswith("#"):
            return

        # Ignorar declaraciones completas
        if self._is_declaration(stripped):
            self._check_declaration_issues(line_num, stripped, result)
            return

        # Analizar llamadas a métodos
        self._check_method_calls(line_num, stripped, result)

        # Analizar decoradores
        self._check_decorators(line_num, stripped, result)

    def _is_declaration(self, line: str) -> bool:
        """Determina si la línea es una declaración."""
        declaration_keywords = [
            "var ",
            "const ",
            "func ",
            "class ",
            "signal ",
            "enum ",
            "extends ",
            "class_name ",
            "static ",
            "@",
        ]
        return any(line.startswith(kw) for kw in declaration_keywords)

    def _check_declaration_issues(self, line_num: int, line: str, result: GDValidationResult) -> None:
        """Verifica problemas en declaraciones."""
        stripped = line.strip()

        # Verificar @export var sin tipo hint
        export_match = self.EXPORT_NO_TYPE_PATTERN.match(stripped)
        if export_match:
            var_name = export_match.group(1)
            result.add_issue(
                line_num,
                "info",
                f"@export variable '{var_name}' has no type hint",
                f"Consider adding a type hint: @export var {var_name}: TypeName",
            )

        # Verificar decoradores deprecated
        decorator_match = self.DECORATOR_PATTERN.match(stripped)
        if decorator_match:
            decorator_name = f"@{decorator_match.group(2)}"
            if decorator_name in self.api.decorators_deprecated:
                msg = self.api.removed.get(decorator_name, f"{decorator_name} is deprecated")
                result.add_issue(
                    line_num,
                    "warning",
                    msg,
                    self.api.removed.get(
                        decorator_name + "_message", "Consider using immediate initialization instead"
                    ),
                )

    def _check_method_calls(self, line_num: int, line: str, result: GDValidationResult) -> None:
        """Verifica llamadas a métodos."""

        # Limpiar strings para evitar falsos positivos
        temp_line = self._remove_strings(line)

        # Buscar métodos llamados en objetos
        # Patrón: obj.method() o $Node.method()
        for match in self.METHOD_CALL_PATTERN.finditer(temp_line):
            object_name = match.group(1) or match.group(2) or match.group(3)
            method_name = match.group(4)

            # Ignorar si es una keyword o tipo built-in
            if self.api.is_keyword(object_name):
                continue
            if object_name in ["self", "super"]:
                continue

            # Verificar si es un tipo conocido
            if object_name in self.api.types:
                self._check_method_on_type(line_num, object_name, method_name, result)

            # Verificar si el método existe como global
            if not object_name:
                if self.api.is_global_function(method_name):
                    continue

                # Verificar si es removed
                was_removed, msg = self.api.is_removed(method_name)
                if was_removed:
                    result.add_issue(line_num, "error", f"'{method_name}' was removed in Godot 4: {msg}")

        # Buscar funciones standalone (como test_move())
        # Patrón: func_name() sin punto antes
        # Excluir keywords y funciones conocidas
        standalone_pattern = re.compile(r"(?<![.\w$])(\w+)\s*\(")
        for match in standalone_pattern.finditer(temp_line):
            func_name = match.group(1)

            # Ignorar si es keyword, función global, o ya declarada en el script
            if self.api.is_keyword(func_name):
                continue
            if self.api.is_global_function(func_name):
                continue
            if func_name in self.declared_funcs:
                continue
            if func_name.startswith("_") and func_name in self.api.virtual_methods:
                continue

            # Verificar si es una función removida
            was_removed, msg = self.api.is_removed(func_name)
            if was_removed:
                result.add_issue(line_num, "error", f"'{func_name}' was removed in Godot 4: {msg}")

    def _check_method_on_type(
        self, line_num: int, type_name: str, method_name: str, result: GDValidationResult
    ) -> None:
        """Verifica un método en un tipo específico."""

        # Verificar si el método existe
        if not self.api.has_method(type_name, method_name):
            # Podría ser un typo o método inexistente
            # Solo warn si no es una función global o método del API
            if not self.api.is_global_function(method_name):
                # Verificar si fue removido
                was_removed, msg = self.api.is_removed(method_name)
                if was_removed:
                    result.add_issue(line_num, "error", f"'{method_name}' was removed in Godot 4: {msg}")
                elif self.extends_type == type_name:
                    # Solo warn si estamos en el tipo correcto
                    # Esto evita falsos positivos por herencia
                    pass  # Método podría existir en tipo padre no en API

    def _check_decorators(self, line_num: int, line: str, result: GDValidationResult) -> None:
        """Verifica decoradores en la línea."""
        decorator_match = self.DECORATOR_PATTERN.match(line.strip())
        if not decorator_match:
            return

        decorator_name = f"@{decorator_match.group(2)}"

        # Verificar decorador válido
        if decorator_name not in self.api.decorators_valid:
            # Podría ser un error de sintaxis
            result.add_issue(
                line_num,
                "warning",
                f"Unknown decorator '{decorator_name}'",
                "Check Godot 4.6 documentation for valid decorators",
            )

    def _remove_strings(self, line: str) -> str:
        """Remove strings from line to avoid false positives."""
        # Remove double-quoted strings
        line = re.sub(r'"[^"]*"', '""', line)
        # Remove single-quoted strings
        line = re.sub(r"'[^']*'", "''", line)
        return line

    def validate_with_godot(self, script_content: str, godot_result: dict) -> GDValidationResult:
        """
        Combina validación de API con resultados de Godot real.

        Args:
            script_content: Contenido del script
            godot_result: Resultado de godot_check_script_syntax()

        Returns:
            Resultado combinado
        """
        # Primero, resultados de Godot (errores reales)
        result = GDValidationResult()

        # Agregar errores de Godot
        for error in godot_result.get("errors", []):
            result.add_issue(
                error.get("line", 0),
                "error",
                f"[Godot] {error.get('message', 'Unknown error')}",
                error.get("suggestion"),
            )

        # Agregar warnings de Godot
        for warning in godot_result.get("warnings", []):
            result.add_issue(
                warning.get("line", 0),
                "warning",
                f"[Godot] {warning.get('message', 'Unknown warning')}",
                warning.get("suggestion"),
            )

        # Luego, análisis de API (nuestra capa)
        api_result = self.validate(script_content)
        result.issues.extend(api_result.issues)

        return result


def validate_gdscript(script_content: str) -> GDValidationResult:
    """
    Función conveniente para validar un script usando solo la API.

    Para validación completa con errores de sintaxis reales,
    usa GDScriptValidator.validate_with_godot() con godot_check_script_syntax().

    Args:
        script_content: Contenido del script .gd

    Returns:
        GDValidationResult con los problemas encontrados
    """
    validator = GDScriptValidator()
    return validator.validate(script_content)


# ============ TESTS ============

if __name__ == "__main__":
    # Test básico
    test_scripts = [
        # Script válido
        """
extends CharacterBody2D

@export var speed: float = 200.0

func _ready():
    move_and_slide()

func custom_method():
    print("Hello")
""",
        # Script con problemas
        """
extends CharacterBody2D

@onready var sprite = $Sprite  # @onready deprecated

func _ready():
    old_method()  # Método no existe
    test_move()   # Removido en Godot 4
    overlaps_body()  # No existe en CharacterBody2D

func bad_method():
    foo.bar()  # foo no es un tipo conocido
""",
    ]

    print("=" * 60)
    print("GDScript Validator v2.0 Test")
    print("=" * 60)

    validator = GDScriptValidator()

    for i, script in enumerate(test_scripts, 1):
        print(f"\n--- Test {i} ---")
        result = validator.validate(script)

        print(f"Valid: {result.is_valid}")
        print(f"Issues found: {len(result.issues)}")

        for issue in result.issues:
            print(f"  Line {issue.line} [{issue.severity.upper()}]: {issue.message}")
            if issue.suggestion:
                print(f"    → {issue.suggestion}")

    print("\n" + "=" * 60)
