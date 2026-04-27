"""
API de Godot para validación de GDScript.

Este módulo proporciona acceso a la información de la API de Godot 4.6.1
para validar scripts contra los métodos, propiedades y tipos conocidos.

Uso:
    from godot_mcp.core.api import GodotAPI

    api = GodotAPI()
    if api.has_method("CharacterBody2D", "move_and_slide"):
        print("Método válido")
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class GodotType:
    """Representa un tipo de Godot (nodo o tipo integrado)."""

    name: str
    methods: list[str] = field(default_factory=list)
    properties: list[str] = field(default_factory=list)
    signals: list[str] = field(default_factory=list)
    extends_hint: Optional[str] = None
    is_node: bool = False
    is_singleton: bool = False


class GodotAPI:
    """
    Interface para acceder a la API de Godot 4.6.1.

    Carga la información de la API desde un archivo JSON y proporciona
    métodos para consultar métodos, propiedades y tipos conocidos.

    Attributes:
        version: Versión de Godot (ej: "4.6.1")
        types: Diccionario de tipos por nombre
        removed: Métodos/propiedades eliminados en Godot 4
    """

    _instance: Optional[GodotAPI] = None

    def __init__(self, api_path: Optional[str] = None):
        """
        Inicializa la API de Godot.

        Args:
            api_path: Ruta al archivo JSON de la API. Si es None, busca
                     en el directorio del módulo.
        """
        self.version: str = ""
        self.types: dict[str, GodotType] = {}
        self.global_functions: dict[str, dict] = {}
        self.decorators_valid: list[str] = []
        self.decorators_deprecated: list[str] = []
        self.virtual_methods: set[str] = set()
        self.keywords: set[str] = set()
        self.removed: dict[str, str] = {}
        self._loaded: bool = False

        self._load(api_path)

    @classmethod
    def get_instance(cls) -> GodotAPI:
        """Obtiene la instancia singleton del API."""
        if cls._instance is None:
            cls._instance = GodotAPI()
        return cls._instance

    def _load(self, api_path: Optional[str] = None) -> None:
        """Carga la API desde el archivo JSON."""
        if self._loaded:
            return

        if api_path is None:
            # Buscar en el directorio del módulo
            module_dir = os.path.dirname(os.path.dirname(__file__))
            api_path = os.path.join(module_dir, "api", "godot_api_4.6.json")

        if not os.path.exists(api_path):
            raise FileNotFoundError(f"API file not found: {api_path}")

        with open(api_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.version = data.get("version", "unknown")

        # Cargar tipos de nodos
        for type_name, type_data in data.get("nodes", {}).items():
            self.types[type_name] = GodotType(
                name=type_name,
                methods=type_data.get("methods", []),
                properties=type_data.get("properties", []),
                signals=type_data.get("signals", []),
                extends_hint=type_data.get("extends_hint"),
                is_node=True,
            )

        # Cargar tipos integrados
        for type_name, type_data in data.get("builtin_types", {}).items():
            self.types[type_name] = GodotType(
                name=type_name,
                methods=type_data.get("methods", []),
                properties=type_data.get("properties", []),
            )

        # Cargar singletons
        for name, methods in data.get("singletons", {}).items():
            self.types[name] = GodotType(name=name, methods=methods.get("methods", []), is_singleton=True)

        # Funciones globales
        self.global_functions = data.get("global_functions", {})

        # Decoradores
        self.decorators_valid = data.get("decorators", {}).get("valid", [])
        self.decorators_deprecated = data.get("decorators", {}).get("deprecated", [])

        # Métodos virtuales
        self.virtual_methods = set(data.get("virtual_methods", []))

        # Keywords
        self.keywords = set(data.get("keywords", []))

        # Removidos
        self.removed = data.get("removed_in_godot4", {})

        self._loaded = True

    def has_method(self, type_name: str, method_name: str) -> bool:
        """
        Verifica si un método existe en un tipo.

        Args:
            type_name: Nombre del tipo (ej: "CharacterBody2D")
            method_name: Nombre del método (ej: "move_and_slide")

        Returns:
            True si el método existe, False en caso contrario
        """
        # Verificar en funciones globales
        if method_name in self.global_functions:
            return True

        # Buscar en el tipo
        type_info = self.types.get(type_name)
        if type_info:
            if method_name in type_info.methods:
                return True
            # Buscar en tipos padre (herencia básica)
            if type_info.extends_hint:
                return self.has_method(type_info.extends_hint, method_name)

        return False

    def has_property(self, type_name: str, property_name: str) -> bool:
        """
        Verifica si una propiedad existe en un tipo.

        Args:
            type_name: Nombre del tipo
            property_name: Nombre de la propiedad

        Returns:
            True si la propiedad existe
        """
        type_info = self.types.get(type_name)
        if type_info:
            if property_name in type_info.properties:
                return True
            if type_info.extends_hint:
                return self.has_property(type_info.extends_hint, property_name)

        return False

    def has_signal(self, type_name: str, signal_name: str) -> bool:
        """Verifica si una señal existe en un tipo."""
        type_info = self.types.get(type_name)
        if type_info:
            if signal_name in type_info.signals:
                return True
            if type_info.extends_hint:
                return self.has_signal(type_info.extends_hint, signal_name)

        return False

    def is_global_function(self, name: str) -> bool:
        """Verifica si es una función global de Godot."""
        return name in self.global_functions

    def is_virtual_method(self, name: str) -> bool:
        """Verifica si es un método virtual de Godot."""
        return name in self.virtual_methods

    def is_keyword(self, name: str) -> bool:
        """Verifica si es una keyword de GDScript."""
        return name in self.keywords

    def is_decorator(self, name: str) -> bool:
        """Verifica si es un decorador válido."""
        return name in self.decorators_valid

    def is_removed(self, name: str) -> tuple[bool, str]:
        """
        Verifica si algo fue removido en Godot 4.

        Returns:
            Tupla (was_removed, message)
        """
        if name in self.removed:
            return True, self.removed[name]
        return False, ""

    def get_method_info(self, name: str) -> Optional[dict]:
        """Obtiene información sobre una función global."""
        return self.global_functions.get(name)

    def get_inheritance_chain(self, type_name: str) -> list[str]:
        """
        Obtiene la cadena de herencia de un tipo.

        Returns:
            Lista de tipos desde el actual hasta Object/Node
        """
        chain = [type_name]
        type_info = self.types.get(type_name)

        while type_info and type_info.extends_hint:
            chain.append(type_info.extends_hint)
            type_info = self.types.get(type_info.extends_hint)

        return chain


# Instancia global para uso directo
_default_api: Optional[GodotAPI] = None


def get_godot_api() -> GodotAPI:
    """Obtiene la API de Godot (singleton)."""
    global _default_api
    if _default_api is None:
        _default_api = GodotAPI()
    return _default_api


# =============================================================================
# NodeAPI - API de tipos de nodos para validación TSCN
# =============================================================================


class NodeAPI:
    """
    Interface para acceder a los tipos de nodos de Godot 4.6.1.

    Proporciona validación de tipos de nodos y detección de tipos
    deprecados o removidos.

    Usage:
        from godot_mcp.core.api import NodeAPI

        api = NodeAPI()
        if api.is_valid_node_type("CharacterBody2D"):
            print("Tipo válido")
        if api.is_removed_node("KinematicBody2D"):
            print("Tipo removido - usar CharacterBody2D")
    """

    _instance: Optional["NodeAPI"] = None

    def __init__(self, nodes_path: Optional[str] = None):
        """
        Inicializa la API de nodos.

        Args:
            nodes_path: Ruta al archivo JSON de nodos. Si es None, busca
                       en el directorio del módulo.
        """
        self.version: str = ""
        self._loaded: bool = False

        # Todas los tipos de nodos válidos en un set para búsqueda O(1)
        self._valid_types: set[str] = set()

        # Mapa de tipos removidos
        self._removed_types: dict[str, dict] = {}

        # Mapa de tipos deprecados
        self._deprecated_types: dict[str, dict] = {}

        # Recursos que NO son nodos
        self._resources_not_nodes: set[str] = set()

        # Categorías
        self._categories: dict[str, str] = {}

        self._load(nodes_path)

    @classmethod
    def get_instance(cls) -> "NodeAPI":
        """Obtiene la instancia singleton del API."""
        if cls._instance is None:
            cls._instance = NodeAPI()
        return cls._instance

    def _load(self, nodes_path: Optional[str] = None) -> None:
        """Carga la información de nodos desde el archivo JSON."""
        if self._loaded:
            return

        if nodes_path is None:
            # Buscar en el directorio del módulo
            module_dir = os.path.dirname(os.path.dirname(__file__))
            nodes_path = os.path.join(module_dir, "api", "godot_nodes_4.6.json")

        if not os.path.exists(nodes_path):
            # Si no existe, usar lista mínima de compatibilidad
            self._use_fallback()
            return

        try:
            with open(nodes_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.version = data.get("_metadata", {}).get("version", "unknown")

            # Cargar categorías
            categories = data.get("valid_node_types", {}).get("_categories", {})
            self._categories = categories

            # Cargar todos los tipos válidos
            valid_types_data = data.get("valid_node_types", {})
            for category, types_list in valid_types_data.items():
                if category.startswith("_"):
                    continue  # Saltar metadatos
                if isinstance(types_list, list):
                    self._valid_types.update(types_list)

            # Cargar tipos removidos
            self._removed_types = data.get("removed_node_types", {})

            # Cargar tipos deprecados
            self._deprecated_types = data.get("deprecated_node_types", {})

            # Cargar recursos que NO son nodos
            resources_data = data.get("resources_not_nodes", {})
            for category, resources_list in resources_data.items():
                if category.startswith("_"):
                    continue
                if isinstance(resources_list, list):
                    self._resources_not_nodes.update(resources_list)

            self._loaded = True

        except (json.JSONDecodeError, IOError) as e:
            # En caso de error, usar fallback
            self._use_fallback()

    def _use_fallback(self) -> None:
        """Usa una lista mínima de tipos de nodos como fallback."""
        self.version = "4.6.1 (fallback)"

        # Lista mínima de tipos conocidos que siempre son válidos
        self._valid_types = {
            # Base
            "Node",
            "Node2D",
            "Node3D",
            "Control",
            "CanvasItem",
            "CanvasLayer",
            "CollisionObject2D",
            "CollisionObject3D",
            "PhysicsBody2D",
            "PhysicsBody3D",
            # Physics 2D
            "StaticBody2D",
            "RigidBody2D",
            "CharacterBody2D",
            "Area2D",
            "PhysicalBone2D",
            "VehicleBody2D",
            "VehicleWheel2D",
            "SoftBody2D",
            # Physics 3D
            "StaticBody3D",
            "RigidBody3D",
            "CharacterBody3D",
            "AnimatableBody3D",
            "Area3D",
            "PhysicalBone3D",
            "SoftBody3D",
            "VehicleBody3D",
            "VehicleWheel3D",
            # Collision
            "CollisionShape2D",
            "CollisionPolygon2D",
            "CollisionShape3D",
            "CollisionPolygon3D",
            "RayCast2D",
            "RayCast3D",
            "ShapeCast2D",
            "ShapeCast3D",
            # 2D Nodes
            "Sprite2D",
            "AnimatedSprite2D",
            "Label",
            "Label3D",
            "TextureRect",
            "TextureButton",
            "NinePatchRect",
            "Line2D",
            "Polygon2D",
            "Path2D",
            "PathFollow2D",
            "ParallaxBackground",
            "ParallaxLayer",
            # 3D Nodes
            "Sprite3D",
            "MeshInstance3D",
            "ImporterMeshInstance3D",
            "VoxelGI",
            "LightmapGI",
            "ReflectionProbe",
            "Decal",
            "FogVolume",
            "WorldEnvironment",
            "Camera3D",
            "Path3D",
            "PathFollow3D",
            # UI
            "Button",
            "CheckBox",
            "CheckButton",
            "RadioButton",
            "OptionButton",
            "MenuButton",
            "SpinBox",
            "HSlider",
            "VSlider",
            "ScrollBar",
            "ProgressBar",
            "LineEdit",
            "TextEdit",
            "RichTextLabel",
            "CodeEdit",
            "ItemList",
            "Tree",
            "TabContainer",
            "Tabs",
            "PopupMenu",
            "FileDialog",
            "ColorPicker",
            "ConfirmationDialog",
            "AcceptDialog",
            "Window",
            "Viewport",
            "SubViewport",
            # Containers
            "CenterContainer",
            "VBoxContainer",
            "HBoxContainer",
            "GridContainer",
            "BoxContainer",
            "MarginContainer",
            "Panel",
            "PanelContainer",
            "ColorRect",
            "SplitContainer",
            "HSplitContainer",
            "VSplitContainer",
            "ScrollContainer",
            "AspectRatioContainer",
            "FlowContainer",
            "HFlowContainer",
            "VFlowContainer",
            # Navigation
            "NavigationAgent2D",
            "NavigationAgent3D",
            "NavigationRegion2D",
            "NavigationRegion3D",
            "NavigationLink2D",
            "NavigationLink3D",
            "NavigationObstacle2D",
            "NavigationObstacle3D",
            # Animation
            "AnimationPlayer",
            "AnimationTree",
            "AnimationMixer",
            "Skeleton2D",
            "Skeleton3D",
            "Bone2D",
            "BoneAttachment3D",
            # Audio
            "AudioStreamPlayer",
            "AudioStreamPlayer2D",
            "AudioStreamPlayer3D",
            "AudioListener2D",
            "AudioListener3D",
            # Lights
            "Light2D",
            "Light3D",
            "DirectionalLight2D",
            "DirectionalLight3D",
            "OmniLight3D",
            "SpotLight3D",
            "PointLight2D",
            # Particles
            "CPUParticles2D",
            "CPUParticles3D",
            "GPUParticles2D",
            "GPUParticles3D",
            # Tilemaps
            "TileMap",
            "TileMapLayer",
            "GridMap",
            # Utilities
            "Timer",
            "Tween",
            "RemoteTransform2D",
            "RemoteTransform3D",
            "VisibilityNotifier2D",
            "VisibilityNotifier3D",
            "VisibleOnScreenNotifier2D",
            "VisibleOnScreenNotifier3D",
            "Marker2D",
            "Marker3D",
            "HTTPRequest",
            "MultiplayerSpawner",
            "MultiplayerSynchronizer",
            # XR
            "XROrigin3D",
            "XRCamera3D",
            "XRController3D",
            "XRAnchor3D",
            # IK
            "CCDIK3D",
            "ChainIK3D",
            "FABRIK3D",
            "SkeletonIK3D",
            # Other
            "CanvasGroup",
            "BackBufferCopy",
            "ReferenceRect",
            "GraphEdit",
            "GraphNode",
        }

        # Tipos removidos
        self._removed_types = {
            "KinematicBody2D": {
                "name": "KinematicBody2D",
                "replacement": "CharacterBody2D",
                "reason": "Renamed in Godot 4",
            },
            "KinematicBody3D": {
                "name": "KinematicBody3D",
                "replacement": "CharacterBody3D",
                "reason": "Renamed in Godot 4",
            },
        }

        self._loaded = True

    def is_valid_node_type(self, type_name: str) -> bool:
        """
        Verifica si un tipo de nodo es válido en Godot 4.6.

        Args:
            type_name: Nombre del tipo (ej: "CharacterBody2D")

        Returns:
            True si el tipo existe y es un nodo válido
        """
        return type_name in self._valid_types

    def is_removed_node(self, type_name: str) -> tuple[bool, str]:
        """
        Verifies if a node type was removed in Godot 4.

        Args:
            type_name: Node type name (e.g., "KinematicBody2D")

        Returns:
            Tuple (was_removed, message)
        """
        # Check direct match first
        if type_name in self._removed_types:
            info = self._removed_types[type_name]
            message = f"'{type_name}' was removed in Godot 4. Use '{info.get('replacement', 'N/A')}' instead. Reason: {info.get('reason', 'Unknown')}"
            return True, message

        # Also check lowercase keys (for JSON with lowercase keys)
        type_lower = type_name.lower()
        for key, info in self._removed_types.items():
            if key.startswith("_"):
                continue  # Skip metadata keys
            if info.get("name", "").lower() == type_lower:
                message = f"'{type_name}' was removed in Godot 4. Use '{info.get('replacement', 'N/A')}' instead. Reason: {info.get('reason', 'Unknown')}"
                return True, message

        return False, ""

    def is_deprecated_node(self, type_name: str) -> tuple[bool, str]:
        """
        Verifies if a node type is deprecated.

        Args:
            type_name: Node type name

        Returns:
            Tuple (is_deprecated, message)
        """
        # Check direct match first
        if type_name in self._deprecated_types:
            info = self._deprecated_types[type_name]
            message = f"'{type_name}' is deprecated. Replacement: '{info.get('replacement', 'N/A')}'"
            return True, message

        # Also check lowercase keys
        type_lower = type_name.lower()
        for key, info in self._deprecated_types.items():
            if key.startswith("_"):
                continue
            if info.get("name", "").lower() == type_lower:
                message = f"'{type_name}' is deprecated. Replacement: '{info.get('replacement', 'N/A')}'"
                return True, message

        return False, ""

    def is_resource_not_node(self, type_name: str) -> bool:
        """
        Verifica si un tipo es un recurso, NO un nodo.

        Algunos tipos como "RectangleShape2D" o "NavigationMesh" son recursos,
        no nodos, y no deben usarse como tipo de nodo en TSCN.

        Args:
            type_name: Nombre del tipo

        Returns:
            True si es un recurso (no un nodo)
        """
        return type_name in self._resources_not_nodes

    def get_replacement(self, removed_type: str) -> Optional[str]:
        """
        Gets the replacement type for a removed one.

        Args:
            removed_type: Removed type name

        Returns:
            Replacement type name or None
        """
        # Check direct match
        info = self._removed_types.get(removed_type)
        if info:
            return info.get("replacement")

        # Check lowercase keys
        type_lower = removed_type.lower()
        for key, info in self._removed_types.items():
            if key.startswith("_"):
                continue
            if info.get("name", "").lower() == type_lower:
                return info.get("replacement")

        return None

    def get_all_valid_types(self) -> set[str]:
        """Obtiene todos los tipos de nodos válidos."""
        return self._valid_types.copy()

    def get_categories(self) -> dict[str, str]:
        """Obtiene las categorías disponibles."""
        return self._categories.copy()

    def validate_type(self, type_name: str) -> dict:
        """
        Validación completa de un tipo de nodo.

        Returns:
            Dict con:
            - is_valid: bool
            - issues: list de problemas encontrados
            - suggestions: list de sugerencias
        """
        result = {"is_valid": False, "issues": [], "suggestions": []}

        # Check removed
        is_removed, msg = self.is_removed_node(type_name)
        if is_removed:
            result["issues"].append(msg)
            replacement = self.get_replacement(type_name)
            if replacement:
                result["suggestions"].append(f"Replace with: {replacement}")
            return result

        # Check deprecated
        is_deprecated, msg = self.is_deprecated_node(type_name)
        if is_deprecated:
            result["issues"].append(msg)
            result["suggestions"].append(msg)

        # Check if it's a resource, not a node
        if self.is_resource_not_node(type_name):
            result["issues"].append(
                f"'{type_name}' is a resource type, not a node type. Do not use it as a node type in TSCN files."
            )
            return result

        # Check if valid
        if self.is_valid_node_type(type_name):
            result["is_valid"] = True
        else:
            # Unknown type - could be a custom class
            result["issues"].append(
                f"'{type_name}' is not a known Godot 4.6 node type. This may be a custom class_name or an invalid type."
            )
            # Don't block - custom class_names are valid

        return result


# Instancia global para uso directo
_default_node_api: Optional[NodeAPI] = None


def get_node_api() -> NodeAPI:
    """Obtiene la API de nodos (singleton)."""
    global _default_node_api
    if _default_node_api is None:
        _default_node_api = NodeAPI()
    return _default_node_api
