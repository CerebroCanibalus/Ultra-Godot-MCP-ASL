"""
Property Tools - Herramienta unificada para manipular propiedades del inspector.

Proporciona una sola herramienta `set_node_properties` que permite al Agente
manejar cualquier propiedad del inspector de cualquier nodo, incluyendo:
- Shapes para CollisionShape2D (auto-crea SubResource)
- Texturas para Sprite2D (auto-crea ExtResource)
- Scripts, materiales, audio streams, etc.
- Propiedades simples (texto, colores, números, vectores)
"""

import logging
import os
from typing import Any, Optional

from godot_mcp.core.tscn_parser import (
    Scene,
    SceneNode,
    ExtResource,
    SubResource,
    parse_tscn,
)
from godot_mcp.tools.node_tools import (
    _ensure_tscn_path,
    _update_scene_file,
    _find_node_by_path,
    _generate_resource_id,
    _clean_resource_id,
    _process_resource_properties,
)
from godot_mcp.tools.decorators import require_session

logger = logging.getLogger(__name__)


# ============ PROPERTY SCHEMAS ============

# Define qué propiedades acepta cada tipo de nodo y qué tipo de valor esperan.
# Formato: {property_name: {"type": <godot_type>, "resource_type": <optional>, "enum": <optional>}}
#
# Tipos especiales:
#   - "ext_resource": requiere un archivo res://, crea ExtResource automáticamente
#   - "sub_resource": crea un SubResource embebido automáticamente
#   - "resource": propiedad que acepta Shape2D, Material, etc. (auto-detecta)

NODE_PROPERTY_SCHEMAS: dict[str, dict[str, dict]] = {
    # --- Physics: Collision Shapes ---
    "CollisionShape2D": {
        "shape": {"type": "sub_resource", "resource_type": "Shape2D", "required": True},
        "disabled": {"type": "bool"},
        "one_way_collision": {"type": "bool"},
        "one_way_collision_margin": {"type": "float"},
    },
    "CollisionShape3D": {
        "shape": {"type": "sub_resource", "resource_type": "Shape3D", "required": True},
        "disabled": {"type": "bool"},
    },
    "CollisionPolygon2D": {
        "polygon": {"type": "PackedVector2Array"},
        "build_mode": {"type": "int", "enum": {"SOLID": 0, "SEGMENTS": 1}},
        "one_way_collision": {"type": "bool"},
        "one_way_collision_margin": {"type": "float"},
    },
    "CollisionPolygon3D": {
        "polygon": {"type": "PackedVector3Array"},
        "depth": {"type": "float"},
    },
    # --- Physics: Bodies ---
    "Area2D": {
        "monitoring": {"type": "bool"},
        "monitorable": {"type": "bool"},
        "collision_layer": {"type": "int"},
        "collision_mask": {"type": "int"},
        "gravity_point": {"type": "bool"},
        "gravity_point_center": {"type": "Vector2"},
        "gravity_point_unit_distance": {"type": "float"},
        "gravity_vec": {"type": "Vector2"},
        "gravity_space_override": {
            "type": "int",
            "enum": {
                "AREA_SPACE_OVERRIDE_DISABLED": 0,
                "AREA_SPACE_OVERRIDE_REPLACE": 1,
                "AREA_SPACE_OVERRIDE_COMBINE": 2,
                "AREA_SPACE_OVERRIDE_COMBINE_REPLACE": 3,
                "AREA_SPACE_OVERRIDE_REPLACE_COMBINE": 4,
            },
        },
        "priority": {"type": "int"},
    },
    "Area3D": {
        "monitoring": {"type": "bool"},
        "monitorable": {"type": "bool"},
        "collision_layer": {"type": "int"},
        "collision_mask": {"type": "int"},
        "gravity_point": {"type": "bool"},
        "gravity_point_center": {"type": "Vector3"},
        "gravity_vec": {"type": "Vector3"},
        "priority": {"type": "int"},
    },
    "RigidBody2D": {
        "mass": {"type": "float"},
        "inertia": {"type": "float"},
        "center_of_mass_mode": {
            "type": "int",
            "enum": {"CENTER_OF_MASS_MODE_AUTO": 0, "CENTER_OF_MASS_MODE_CUSTOM": 1},
        },
        "center_of_mass": {"type": "Vector2"},
        "physics_material_override": {
            "type": "sub_resource",
            "resource_type": "PhysicsMaterial",
        },
        "gravity_scale": {"type": "float"},
        "custom_integrator": {"type": "bool"},
        "continuous_cd": {
            "type": "int",
            "enum": {
                "CCD_MODE_DISABLED": 0,
                "CCD_MODE_CAST_RAY": 1,
                "CCD_MODE_CAST_SHAPE": 2,
            },
        },
        "max_contacts_reported": {"type": "int"},
        "contact_monitor": {"type": "bool"},
        "sleeping": {"type": "bool"},
        "freeze": {"type": "bool"},
        "freeze_mode": {
            "type": "int",
            "enum": {"FREEZE_MODE_KEEP_POSITION": 0, "FREEZE_MODE_STATIC": 1},
        },
        "linear_velocity": {"type": "Vector2"},
        "angular_velocity": {"type": "float"},
        "linear_damp": {"type": "float"},
        "angular_damp": {"type": "float"},
        "mode": {
            "type": "int",
            "enum": {"RIGID": 0, "STATIC": 1, "CHARACTER": 2, "KINEMATIC": 3},
        },
        "axis_lock_linear_x": {"type": "bool"},
        "axis_lock_linear_y": {"type": "bool"},
        "axis_lock_angular_z": {"type": "bool"},
        "lock_rotation": {"type": "bool"},
        "can_sleep": {"type": "bool"},
    },
    "RigidBody3D": {
        "mass": {"type": "float"},
        "inertia": {"type": "Vector3"},
        "physics_material_override": {
            "type": "sub_resource",
            "resource_type": "PhysicsMaterial",
        },
        "gravity_scale": {"type": "float"},
        "continuous_cd": {"type": "int"},
        "max_contacts_reported": {"type": "int"},
        "contact_monitor": {"type": "bool"},
        "sleeping": {"type": "bool"},
        "freeze": {"type": "bool"},
        "linear_velocity": {"type": "Vector3"},
        "angular_velocity": {"type": "Vector3"},
        "linear_damp": {"type": "float"},
        "angular_damp": {"type": "float"},
        "mode": {
            "type": "int",
            "enum": {"RIGID": 0, "STATIC": 1, "CHARACTER": 2, "KINEMATIC": 3},
        },
        "lock_rotation": {"type": "bool"},
        "can_sleep": {"type": "bool"},
    },
    "CharacterBody2D": {
        "motion_mode": {
            "type": "int",
            "enum": {"MOTION_MODE_GROUNDED": 0, "MOTION_MODE_FLOATING": 1},
        },
        "up_direction": {"type": "Vector2"},
        "floor_max_angle": {"type": "float"},
        "floor_constant_speed": {"type": "float"},
        "floor_block_on_wall": {"type": "bool"},
        "floor_snap_length": {"type": "float"},
        "platform_on_leave": {
            "type": "int",
            "enum": {
                "PLATFORM_ON_LEAVE_DO_NOTHING": 0,
                "PLATFORM_ON_LEAVE_SET_VELOCITY": 1,
                "PLATFORM_ON_LEAVE_SET_INERTIA": 2,
            },
        },
        "platform_floor_layers": {"type": "int"},
        "platform_wall_layers": {"type": "int"},
        "safe_margin": {"type": "float"},
        "slide_on_ceiling": {"type": "bool"},
        "wall_min_slide_angle": {"type": "float"},
    },
    "CharacterBody3D": {
        "motion_mode": {
            "type": "int",
            "enum": {"MOTION_MODE_GROUNDED": 0, "MOTION_MODE_FLOATING": 1},
        },
        "up_direction": {"type": "Vector3"},
        "floor_max_angle": {"type": "float"},
        "floor_constant_speed": {"type": "float"},
        "floor_block_on_wall": {"type": "bool"},
        "floor_snap_length": {"type": "float"},
        "safe_margin": {"type": "float"},
        "slide_on_ceiling": {"type": "bool"},
        "wall_min_slide_angle": {"type": "float"},
    },
    "StaticBody2D": {
        "physics_material_override": {
            "type": "sub_resource",
            "resource_type": "PhysicsMaterial",
        },
        "constant_linear_velocity": {"type": "Vector2"},
        "constant_angular_velocity": {"type": "float"},
    },
    "StaticBody3D": {
        "physics_material_override": {
            "type": "sub_resource",
            "resource_type": "PhysicsMaterial",
        },
        "constant_linear_velocity": {"type": "Vector3"},
        "constant_angular_velocity": {"type": "Vector3"},
    },
    # --- 2D Rendering ---
    "Sprite2D": {
        "texture": {"type": "ext_resource", "resource_type": "Texture2D"},
        "hframes": {"type": "int"},
        "vframes": {"type": "int"},
        "frame": {"type": "int"},
        "frame_coords": {"type": "Vector2i"},
        "region_enabled": {"type": "bool"},
        "region_rect": {"type": "Rect2"},
        "centered": {"type": "bool"},
        "offset": {"type": "Vector2"},
        "flip_h": {"type": "bool"},
        "flip_v": {"type": "bool"},
        "material_override": {"type": "ext_resource", "resource_type": "Material"},
    },
    "Sprite3D": {
        "texture": {"type": "ext_resource", "resource_type": "Texture2D"},
        "pixel_size": {"type": "float"},
        "centered": {"type": "bool"},
        "offset": {"type": "Vector3"},
        "flip_h": {"type": "bool"},
        "flip_v": {"type": "bool"},
        "material_override": {"type": "ext_resource", "resource_type": "Material"},
    },
    "AnimatedSprite2D": {
        "sprite_frames": {"type": "ext_resource", "resource_type": "SpriteFrames"},
        "animation": {"type": "string"},
        "frame": {"type": "int"},
        "speed_scale": {"type": "float"},
        "playing": {"type": "bool"},
    },
    "AnimatedSprite3D": {
        "sprite_frames": {"type": "ext_resource", "resource_type": "SpriteFrames3D"},
        "animation": {"type": "string"},
        "frame": {"type": "int"},
        "speed_scale": {"type": "float"},
        "playing": {"type": "bool"},
    },
    "TextureRect": {
        "texture": {"type": "ext_resource", "resource_type": "Texture2D"},
        "expand_mode": {
            "type": "int",
            "enum": {
                "IGNORE_SIZE": 0,
                "FIT_WIDTH": 1,
                "FIT_HEIGHT": 2,
                "FIT": 3,
                "KEEP_SIZE": 4,
            },
        },
        "stretch_mode": {
            "type": "int",
            "enum": {
                "SCALE_ON_EXPAND": 0,
                "SCALE": 1,
                "TILE": 2,
                "KEEP": 3,
                "KEEP_CENTERED": 4,
                "KEEP_ASPECT": 5,
                "KEEP_ASPECT_CENTERED": 6,
                "KEEP_ASPECT_COVERED": 7,
            },
        },
        "flip_h": {"type": "bool"},
        "flip_v": {"type": "bool"},
    },
    "TextureButton": {
        "texture_normal": {"type": "ext_resource", "resource_type": "Texture2D"},
        "texture_pressed": {"type": "ext_resource", "resource_type": "Texture2D"},
        "texture_hover": {"type": "ext_resource", "resource_type": "Texture2D"},
        "texture_disabled": {"type": "ext_resource", "resource_type": "Texture2D"},
        "texture_focused": {"type": "ext_resource", "resource_type": "Texture2D"},
        "stretch_mode": {"type": "int"},
        "toggle_mode": {"type": "bool"},
        "button_pressed": {"type": "bool"},
        "disabled": {"type": "bool"},
        "flat": {"type": "bool"},
    },
    "NinePatchRect": {
        "texture": {"type": "ext_resource", "resource_type": "Texture2D"},
        "patch_margin_left": {"type": "int"},
        "patch_margin_right": {"type": "int"},
        "patch_margin_top": {"type": "int"},
        "patch_margin_bottom": {"type": "int"},
        "axis_stretch_horizontal": {
            "type": "int",
            "enum": {"STRETCH": 0, "TILE": 1, "SLICE": 2},
        },
        "axis_stretch_vertical": {
            "type": "int",
            "enum": {"STRETCH": 0, "TILE": 1, "SLICE": 2},
        },
        "draw_center": {"type": "bool"},
    },
    "Polygon2D": {
        "polygon": {"type": "PackedVector2Array"},
        "color": {"type": "Color"},
        "texture": {"type": "ext_resource", "resource_type": "Texture2D"},
        "uv": {"type": "PackedVector2Array"},
    },
    "Line2D": {
        "points": {"type": "PackedVector2Array"},
        "width": {"type": "float"},
        "default_color": {"type": "Color"},
        "joint_mode": {
            "type": "int",
            "enum": {
                "JOINT_MODE_SHARP": 0,
                "JOINT_MODE_CURVE": 1,
                "JOINT_MODE_ROUND": 2,
                "JOINT_MODE_NONE": 3,
            },
        },
        "cap_mode": {
            "type": "int",
            "enum": {"CAP_MODE_NONE": 0, "CAP_MODE_BOX": 1, "CAP_MODE_ROUND": 2},
        },
        "closed": {"type": "bool"},
    },
    "GPUParticles2D": {
        "amount": {"type": "int"},
        "lifetime": {"type": "float"},
        "one_shot": {"type": "bool"},
        "emitting": {"type": "bool"},
        "process_material": {
            "type": "sub_resource",
            "resource_type": "ParticleProcessMaterial",
        },
        "draw_pass_1": {"type": "ext_resource", "resource_type": "Texture2D"},
        "explosiveness_ratio": {"type": "float"},
        "randomness_ratio": {"type": "float"},
        "speed_scale": {"type": "float"},
        "interpolate": {"type": "bool"},
        "local_coords": {"type": "bool"},
    },
    "GPUParticles3D": {
        "amount": {"type": "int"},
        "lifetime": {"type": "float"},
        "one_shot": {"type": "bool"},
        "emitting": {"type": "bool"},
        "process_material": {
            "type": "sub_resource",
            "resource_type": "ParticleProcessMaterial",
        },
        "draw_pass_1": {"type": "ext_resource", "resource_type": "Mesh"},
        "explosiveness_ratio": {"type": "float"},
        "randomness_ratio": {"type": "float"},
        "speed_scale": {"type": "float"},
        "interpolate": {"type": "bool"},
        "local_coords": {"type": "bool"},
    },
    "CPUParticles2D": {
        "amount": {"type": "int"},
        "lifetime": {"type": "float"},
        "one_shot": {"type": "bool"},
        "emitting": {"type": "bool"},
        "speed_scale": {"type": "float"},
        "explosiveness_ratio": {"type": "float"},
        "randomness_ratio": {"type": "float"},
        "local_coords": {"type": "bool"},
    },
    "CPUParticles3D": {
        "amount": {"type": "int"},
        "lifetime": {"type": "float"},
        "one_shot": {"type": "bool"},
        "emitting": {"type": "bool"},
        "speed_scale": {"type": "float"},
        "local_coords": {"type": "bool"},
    },
    # --- 3D Rendering ---
    "MeshInstance3D": {
        "mesh": {"type": "ext_resource", "resource_type": "Mesh"},
        "material_override": {"type": "ext_resource", "resource_type": "Material"},
        "visibility_range_begin": {"type": "float"},
        "visibility_range_end": {"type": "float"},
        "cast_shadow": {
            "type": "int",
            "enum": {
                "SHADOW_CASTING_SETTING_OFF": 0,
                "SHADOW_CASTING_SETTING_ON": 1,
                "SHADOW_CASTING_SETTING_DOUBLE_SIDED": 2,
                "SHADOW_CASTING_SETTING_SHADOWS_ONLY": 3,
            },
        },
        "custom_aabb": {"type": "AABB"},
    },
    "CSGMesh3D": {
        "mesh": {"type": "ext_resource", "resource_type": "Mesh"},
        "material_override": {"type": "ext_resource", "resource_type": "Material"},
        "use_collision": {"type": "bool"},
    },
    "CSGBox3D": {
        "size": {"type": "Vector3"},
        "material_override": {"type": "ext_resource", "resource_type": "Material"},
        "use_collision": {"type": "bool"},
    },
    "CSGSphere3D": {
        "radius": {"type": "float"},
        "height": {"type": "float"},
        "sides": {"type": "int"},
        "bottom_sides": {"type": "int"},
        "top_sides": {"type": "int"},
        "is_hemisphere": {"type": "bool"},
        "material_override": {"type": "ext_resource", "resource_type": "Material"},
        "use_collision": {"type": "bool"},
    },
    "CSGCylinder3D": {
        "radius": {"type": "float"},
        "height": {"type": "float"},
        "sides": {"type": "int"},
        "cone_angle": {"type": "float"},
        "is_cone": {"type": "bool"},
        "material_override": {"type": "ext_resource", "resource_type": "Material"},
        "use_collision": {"type": "bool"},
    },
    "CSGCapsule3D": {
        "radius": {"type": "float"},
        "height": {"type": "float"},
        "sides": {"type": "int"},
        "top_sides": {"type": "int"},
        "material_override": {"type": "ext_resource", "resource_type": "Material"},
        "use_collision": {"type": "bool"},
    },
    "CSGTorus3D": {
        "inner_radius": {"type": "float"},
        "outer_radius": {"type": "float"},
        "sides": {"type": "int"},
        "ring_sides": {"type": "int"},
        "material_override": {"type": "ext_resource", "resource_type": "Material"},
        "use_collision": {"type": "bool"},
    },
    # --- Lights 2D ---
    "Light2D": {
        "texture": {"type": "ext_resource", "resource_type": "Texture2D"},
        "color": {"type": "Color"},
        "energy": {"type": "float"},
        "scale": {"type": "Vector2"},
        "offset": {"type": "Vector2"},
        "mode": {
            "type": "int",
            "enum": {
                "LIGHT_MODE_SHADOWS_ONLY": 0,
                "LIGHT_MODE_LIGHT": 1,
                "LIGHT_MODE_LIGHT_AND_SHADOWS": 2,
            },
        },
        "blend_mode": {
            "type": "int",
            "enum": {"LIGHT_BLEND_MIX": 0, "LIGHT_BLEND_ADD": 1, "LIGHT_BLEND_SUB": 2},
        },
        "shadow_enabled": {"type": "bool"},
        "shadow_color": {"type": "Color"},
        "shadow_filter": {
            "type": "int",
            "enum": {
                "LIGHT_SHADOW_FILTER_NONE": 0,
                "LIGHT_SHADOW_FILTER_PCF_3": 1,
                "LIGHT_SHADOW_FILTER_PCF_5": 2,
                "LIGHT_SHADOW_FILTER_PCF_7": 3,
                "LIGHT_SHADOW_FILTER_PCF_9": 4,
                "LIGHT_SHADOW_FILTER_PCF_13": 5,
            },
        },
        "range_z_min": {"type": "float"},
        "range_z_max": {"type": "float"},
        "range_layer_min": {"type": "float"},
        "range_layer_max": {"type": "float"},
        "height": {"type": "float"},
    },
    "PointLight2D": {
        "color": {"type": "Color"},
        "energy": {"type": "float"},
        "range": {"type": "float"},
        "texture": {"type": "ext_resource", "resource_type": "Texture2D"},
        "shadow_enabled": {"type": "bool"},
        "shadow_color": {"type": "Color"},
        "blend_mode": {
            "type": "int",
            "enum": {"LIGHT_BLEND_MIX": 0, "LIGHT_BLEND_ADD": 1, "LIGHT_BLEND_SUB": 2},
        },
    },
    "DirectionalLight2D": {
        "color": {"type": "Color"},
        "energy": {"type": "float"},
        "shadow_enabled": {"type": "bool"},
        "shadow_color": {"type": "Color"},
        "shadow_filter": {"type": "int"},
        "blend_mode": {
            "type": "int",
            "enum": {"LIGHT_BLEND_MIX": 0, "LIGHT_BLEND_ADD": 1, "LIGHT_BLEND_SUB": 2},
        },
        "height": {"type": "float"},
    },
    # --- Lights 3D ---
    "DirectionalLight3D": {
        "light_color": {"type": "Color"},
        "light_energy": {"type": "float"},
        "light_indirect_energy": {"type": "float"},
        "light_reverse_fade": {"type": "bool"},
        "light_negative": {"type": "bool"},
        "shadow_enabled": {"type": "bool"},
        "shadow_color": {"type": "Color"},
        "shadow_bias": {"type": "float"},
        "shadow_normal_bias": {"type": "float"},
        "shadow_max_distance": {"type": "float"},
        "shadow_split_1_offset": {"type": "float"},
        "shadow_split_2_offset": {"type": "float"},
        "shadow_split_3_offset": {"type": "float"},
        "shadow_blend_mode": {"type": "int"},
    },
    "OmniLight3D": {
        "light_color": {"type": "Color"},
        "light_energy": {"type": "float"},
        "light_indirect_energy": {"type": "float"},
        "light_reverse_fade": {"type": "bool"},
        "light_negative": {"type": "bool"},
        "omni_range": {"type": "float"},
        "omni_attenuation": {"type": "float"},
        "omni_directional_shadow_enabled": {"type": "bool"},
        "shadow_enabled": {"type": "bool"},
        "shadow_color": {"type": "Color"},
        "shadow_bias": {"type": "float"},
        "shadow_normal_bias": {"type": "float"},
        "shadow_max_distance": {"type": "float"},
        "shadow_contact": {"type": "float"},
    },
    "SpotLight3D": {
        "light_color": {"type": "Color"},
        "light_energy": {"type": "float"},
        "light_indirect_energy": {"type": "float"},
        "light_reverse_fade": {"type": "bool"},
        "light_negative": {"type": "bool"},
        "spot_range": {"type": "float"},
        "spot_angle": {"type": "float"},
        "spot_angle_attenuation": {"type": "float"},
        "spot_attenuation": {"type": "float"},
        "shadow_enabled": {"type": "bool"},
        "shadow_color": {"type": "Color"},
        "shadow_bias": {"type": "float"},
        "shadow_normal_bias": {"type": "float"},
        "shadow_max_distance": {"type": "float"},
        "shadow_contact": {"type": "float"},
    },
    # --- Camera ---
    "Camera2D": {
        "current": {"type": "bool"},
        "zoom": {"type": "Vector2"},
        "offset": {"type": "Vector2"},
        "rotation": {"type": "float"},
        "anchor_mode": {
            "type": "int",
            "enum": {"ANCHOR_MODE_DRAG_CENTER": 0, "ANCHOR_MODE_FIXED_TOP_LEFT": 1},
        },
        "position_smoothing_enabled": {"type": "bool"},
        "position_smoothing_speed": {"type": "float"},
        "limit_left": {"type": "int"},
        "limit_top": {"type": "int"},
        "limit_right": {"type": "int"},
        "limit_bottom": {"type": "int"},
        "limit_smoothed": {"type": "bool"},
        "limit_margin_left": {"type": "int"},
        "limit_margin_top": {"type": "int"},
        "limit_margin_right": {"type": "int"},
        "limit_margin_bottom": {"type": "int"},
        "drag_horizontal_enabled": {"type": "bool"},
        "drag_vertical_enabled": {"type": "bool"},
        "drag_horizontal_offset": {"type": "float"},
        "drag_vertical_offset": {"type": "float"},
        "drag_horizontal_margin": {"type": "int"},
        "drag_vertical_margin": {"type": "int"},
        "ignore_rotation": {"type": "bool"},
        "screen_damping_enabled": {"type": "bool"},
        "screen_damping_strength": {"type": "float"},
    },
    "Camera3D": {
        "current": {"type": "bool"},
        "fov": {"type": "float"},
        "size": {"type": "float"},
        "projection": {
            "type": "int",
            "enum": {
                "PROJECTION_PERSPECTIVE": 0,
                "PROJECTION_ORTHOGONAL": 1,
                "PROJECTION_FRUSTUM": 2,
            },
        },
        "near": {"type": "float"},
        "far": {"type": "float"},
        "keep_aspect": {"type": "int", "enum": {"KEEP_WIDTH": 0, "KEEP_HEIGHT": 1}},
        "cull_mask": {"type": "int"},
        "doppler_tracking": {
            "type": "int",
            "enum": {
                "DOPPLER_TRACKING_DISABLED": 0,
                "DOPPLER_TRACKING_IDLE_STEP": 1,
                "DOPPLER_TRACKING_PHYSICS_STEP": 2,
            },
        },
    },
    # --- UI Controls ---
    "Label": {
        "text": {"type": "string"},
        "autowrap_mode": {
            "type": "int",
            "enum": {
                "AUTOWRAP_OFF": 0,
                "AUTOWRAP_ARBITRARY": 1,
                "AUTOWRAP_WORD": 2,
                "AUTOWRAP_WORD_SMART": 3,
            },
        },
        "clip_text": {"type": "bool"},
        "uppercase": {"type": "bool"},
        "percent_visible": {"type": "float"},
        "visible_characters": {"type": "int"},
        "horizontal_alignment": {
            "type": "int",
            "enum": {
                "HORIZONTAL_ALIGNMENT_LEFT": 0,
                "HORIZONTAL_ALIGNMENT_CENTER": 1,
                "HORIZONTAL_ALIGNMENT_RIGHT": 2,
                "HORIZONTAL_ALIGNMENT_FILL": 3,
            },
        },
        "vertical_alignment": {
            "type": "int",
            "enum": {
                "VERTICAL_ALIGNMENT_TOP": 0,
                "VERTICAL_ALIGNMENT_CENTER": 1,
                "VERTICAL_ALIGNMENT_BOTTOM": 2,
                "VERTICAL_ALIGNMENT_FILL": 3,
            },
        },
    },
    "RichTextLabel": {
        "text": {"type": "string"},
        "bbcode_enabled": {"type": "bool"},
        "fit_content": {"type": "bool"},
        "scroll_active": {"type": "bool"},
        "scroll_following": {"type": "bool"},
        "selection_enabled": {"type": "bool"},
        "context_menu_enabled": {"type": "bool"},
        "percent_visible": {"type": "float"},
        "visible_characters": {"type": "int"},
        "uppercase": {"type": "bool"},
        "tab_size": {"type": "int"},
    },
    "Button": {
        "text": {"type": "string"},
        "disabled": {"type": "bool"},
        "toggle_mode": {"type": "bool"},
        "button_pressed": {"type": "bool"},
        "flat": {"type": "bool"},
        "alignment": {
            "type": "int",
            "enum": {
                "HORIZONTAL_ALIGNMENT_LEFT": 0,
                "HORIZONTAL_ALIGNMENT_CENTER": 1,
                "HORIZONTAL_ALIGNMENT_RIGHT": 2,
                "HORIZONTAL_ALIGNMENT_FILL": 3,
            },
        },
        "clip_text": {"type": "bool"},
        "expand_icon": {"type": "bool"},
        "shortcut": {"type": "ext_resource", "resource_type": "Shortcut"},
    },
    "LineEdit": {
        "text": {"type": "string"},
        "placeholder_text": {"type": "string"},
        "editable": {"type": "bool"},
        "secret": {"type": "bool"},
        "secret_character": {"type": "string"},
        "max_length": {"type": "int"},
        "alignment": {
            "type": "int",
            "enum": {
                "HORIZONTAL_ALIGNMENT_LEFT": 0,
                "HORIZONTAL_ALIGNMENT_CENTER": 1,
                "HORIZONTAL_ALIGNMENT_RIGHT": 2,
                "HORIZONTAL_ALIGNMENT_FILL": 3,
            },
        },
        "clear_button_enabled": {"type": "bool"},
        "context_menu_enabled": {"type": "bool"},
    },
    "TextEdit": {
        "text": {"type": "string"},
        "editable": {"type": "bool"},
        "wrap_mode": {
            "type": "int",
            "enum": {
                "TEXT_WRAPPING_NONE": 0,
                "TEXT_WRAPPING_WORD": 1,
                "TEXT_WRAPPING_WORD_BOUNDARY": 2,
            },
        },
        "syntax_highlighter": {
            "type": "ext_resource",
            "resource_type": "SyntaxHighlighter",
        },
        "context_menu_enabled": {"type": "bool"},
    },
    "CodeEdit": {
        "text": {"type": "string"},
        "editable": {"type": "bool"},
        "wrap_mode": {"type": "int"},
        "syntax_highlighter": {
            "type": "ext_resource",
            "resource_type": "SyntaxHighlighter",
        },
    },
    "CheckBox": {
        "text": {"type": "string"},
        "button_pressed": {"type": "bool"},
        "disabled": {"type": "bool"},
        "toggle_mode": {"type": "bool"},
        "flat": {"type": "bool"},
    },
    "CheckButton": {
        "button_pressed": {"type": "bool"},
        "disabled": {"type": "bool"},
        "toggle_mode": {"type": "bool"},
        "flat": {"type": "bool"},
    },
    "OptionButton": {
        "selected": {"type": "int"},
        "disabled": {"type": "bool"},
        "flat": {"type": "bool"},
        "clip_text": {"type": "bool"},
        "fit_to_longest_item": {"type": "bool"},
        "alignment": {"type": "int"},
    },
    "ColorRect": {
        "color": {"type": "Color"},
    },
    "ColorPicker": {
        "color": {"type": "Color"},
        "edit_alpha": {"type": "bool"},
        "picker_shape": {
            "type": "int",
            "enum": {
                "PICKER_SHAPE_HUE_RING": 0,
                "PICKER_SHAPE_HUE_SQUARE": 1,
                "PICKER_SHAPE_HUE_BAR": 2,
            },
        },
        "color_mode": {
            "type": "int",
            "enum": {
                "COLOR_MODE_HSV": 0,
                "COLOR_MODE_HSL": 1,
                "COLOR_MODE_RAW": 2,
                "COLOR_MODE_OKHSL": 3,
                "COLOR_MODE_OKHSV": 4,
            },
        },
        "presets_visible": {"type": "bool"},
    },
    "ColorPickerButton": {
        "color": {"type": "Color"},
        "edit_alpha": {"type": "bool"},
        "popup_title": {"type": "string"},
    },
    "ProgressBar": {
        "value": {"type": "float"},
        "max_value": {"type": "float"},
        "min_value": {"type": "float"},
        "step": {"type": "float"},
        "show_percentage": {"type": "bool"},
    },
    "TextureProgressBar": {
        "value": {"type": "float"},
        "max_value": {"type": "float"},
        "min_value": {"type": "float"},
        "texture_progress": {"type": "ext_resource", "resource_type": "Texture2D"},
        "texture_under": {"type": "ext_resource", "resource_type": "Texture2D"},
        "texture_over": {"type": "ext_resource", "resource_type": "Texture2D"},
        "fill_mode": {
            "type": "int",
            "enum": {
                "FILL_LEFT_TO_RIGHT": 0,
                "FILL_RIGHT_TO_LEFT": 1,
                "FILL_TOP_TO_BOTTOM": 2,
                "FILL_BOTTOM_TO_TOP": 3,
                "FILL_BIDI_HORIZONTAL": 4,
                "FILL_BIDI_VERTICAL": 5,
                "FILL_RADIAL_CLOCKWISE": 6,
                "FILL_RADIAL_COUNTER_CLOCKWISE": 7,
                "FILL_RADIAL_LEFT_TO_RIGHT": 8,
                "FILL_RADIAL_RIGHT_TO_LEFT": 9,
                "FILL_RADIAL_TOP_TO_BOTTOM": 10,
                "FILL_RADIAL_BOTTOM_TO_TOP": 11,
            },
        },
        "radial_initial_angle": {"type": "float"},
        "radial_fill_degrees": {"type": "float"},
        "radial_center_offset": {"type": "Vector2"},
    },
    "HSlider": {
        "value": {"type": "float"},
        "max_value": {"type": "float"},
        "min_value": {"type": "float"},
        "step": {"type": "float"},
        "page": {"type": "float"},
        "tick_count": {"type": "int"},
        "ticks_on_borders": {"type": "bool"},
        "editable": {"type": "bool"},
        "allow_greater": {"type": "bool"},
        "allow_lesser": {"type": "bool"},
    },
    "VSlider": {
        "value": {"type": "float"},
        "max_value": {"type": "float"},
        "min_value": {"type": "float"},
        "step": {"type": "float"},
        "page": {"type": "float"},
        "tick_count": {"type": "int"},
        "ticks_on_borders": {"type": "bool"},
        "editable": {"type": "bool"},
        "allow_greater": {"type": "bool"},
        "allow_lesser": {"type": "bool"},
    },
    "SpinBox": {
        "value": {"type": "float"},
        "max_value": {"type": "float"},
        "min_value": {"type": "float"},
        "step": {"type": "float"},
        "custom_suffix": {"type": "string"},
        "allow_greater": {"type": "bool"},
        "allow_lesser": {"type": "bool"},
        "editable": {"type": "bool"},
        "hide_number": {"type": "bool"},
    },
    "Panel": {},
    "PanelContainer": {},
    "VBoxContainer": {
        "alignment": {"type": "int", "enum": {"BEGIN": 0, "CENTER": 1, "END": 2}},
    },
    "HBoxContainer": {
        "alignment": {"type": "int", "enum": {"BEGIN": 0, "CENTER": 1, "END": 2}},
    },
    "GridContainer": {
        "columns": {"type": "int"},
        "flow_direction": {"type": "int"},
    },
    "MarginContainer": {},
    "CenterContainer": {},
    "ScrollContainer": {
        "horizontal_scroll_mode": {
            "type": "int",
            "enum": {
                "SCROLL_MODE_DISABLED": 0,
                "SCROLL_MODE_AUTO": 1,
                "SCROLL_MODE_ALWAYS": 2,
                "SCROLL_MODE_SHOW_NEVER": 3,
            },
        },
        "vertical_scroll_mode": {
            "type": "int",
            "enum": {
                "SCROLL_MODE_DISABLED": 0,
                "SCROLL_MODE_AUTO": 1,
                "SCROLL_MODE_ALWAYS": 2,
                "SCROLL_MODE_SHOW_NEVER": 3,
            },
        },
        "follow_focus": {"type": "bool"},
    },
    "TabContainer": {
        "current_tab": {"type": "int"},
        "tabs_visible": {"type": "bool"},
        "tab_alignment": {
            "type": "int",
            "enum": {
                "TAB_ALIGNMENT_LEFT": 0,
                "TAB_ALIGNMENT_CENTER": 1,
                "TAB_ALIGNMENT_RIGHT": 2,
            },
        },
        "drag_to_rearrange_enabled": {"type": "bool"},
    },
    "TabBar": {
        "current_tab": {"type": "int"},
        "tabs_visible": {"type": "bool"},
        "tab_alignment": {"type": "int"},
        "drag_to_rearrange_enabled": {"type": "bool"},
    },
    "Tree": {
        "hide_root": {"type": "bool"},
        "allow_rmb_select": {"type": "bool"},
        "allow_reselect": {"type": "bool"},
        "select_mode": {
            "type": "int",
            "enum": {"SELECT_SINGLE": 0, "SELECT_MULTI": 1, "SELECT_ROW": 2},
        },
        "hide_folding": {"type": "bool"},
    },
    "ItemList": {
        "select_mode": {"type": "int", "enum": {"SELECT_SINGLE": 0, "SELECT_MULTI": 1}},
        "max_columns": {"type": "int"},
        "fixed_column_width": {"type": "int"},
        "max_text_lines": {"type": "int"},
        "same_column_width": {"type": "bool"},
        "auto_height": {"type": "bool"},
        "allow_reselect": {"type": "bool"},
        "allow_rmb_select": {"type": "bool"},
    },
    "ReferenceRect": {
        "border_width": {"type": "int"},
        "border_color": {"type": "Color"},
    },
    # --- Audio ---
    "AudioStreamPlayer": {
        "stream": {"type": "ext_resource", "resource_type": "AudioStream"},
        "playing": {"type": "bool"},
        "volume_db": {"type": "float"},
        "pitch_scale": {"type": "float"},
        "autoplay": {"type": "bool"},
        "max_polyphony": {"type": "int"},
        "bus": {"type": "string"},
    },
    "AudioStreamPlayer2D": {
        "stream": {"type": "ext_resource", "resource_type": "AudioStream"},
        "playing": {"type": "bool"},
        "volume_db": {"type": "float"},
        "pitch_scale": {"type": "float"},
        "autoplay": {"type": "bool"},
        "max_distance": {"type": "float"},
        "attenuation": {"type": "float"},
        "bus": {"type": "string"},
    },
    "AudioStreamPlayer3D": {
        "stream": {"type": "ext_resource", "resource_type": "AudioStream"},
        "playing": {"type": "bool"},
        "volume_db": {"type": "float"},
        "pitch_scale": {"type": "float"},
        "autoplay": {"type": "bool"},
        "max_distance": {"type": "float"},
        "attenuation": {"type": "float"},
        "unit_size": {"type": "float"},
        "bus": {"type": "string"},
    },
    # --- Animation ---
    "AnimationPlayer": {
        "autoplay": {"type": "string"},
        "current_animation": {"type": "string"},
        "playback_process_mode": {
            "type": "int",
            "enum": {
                "ANIMATION_PROCESS_MODE_PHYSICS": 0,
                "ANIMATION_PROCESS_MODE_IDLE": 1,
            },
        },
        "playback_default_blend_time": {"type": "float"},
        "playback_speed": {"type": "float"},
    },
    "AnimationTree": {
        "tree_root": {"type": "sub_resource", "resource_type": "AnimationRootNode"},
        "anim_player": {"type": "NodePath"},
        "active": {"type": "bool"},
        "playback_process_mode": {"type": "int"},
    },
    # --- Timer ---
    "Timer": {
        "wait_time": {"type": "float"},
        "one_shot": {"type": "bool"},
        "autostart": {"type": "bool"},
        "paused": {"type": "bool"},
        "process_callback": {
            "type": "int",
            "enum": {"TIMER_PROCESS_PHYSICS": 0, "TIMER_PROCESS_IDLE": 1},
        },
        "timeout": {"type": "float"},
    },
    # --- RayCast ---
    "RayCast2D": {
        "target_position": {"type": "Vector2"},
        "enabled": {"type": "bool"},
        "collision_mask": {"type": "int"},
        "hit_from_inside": {"type": "bool"},
        "hit_back_faces": {"type": "bool"},
        "exclude_parent": {"type": "bool"},
        "debug_shape_custom_color": {"type": "Color"},
    },
    "RayCast3D": {
        "target_position": {"type": "Vector3"},
        "enabled": {"type": "bool"},
        "collision_mask": {"type": "int"},
        "hit_from_inside": {"type": "bool"},
        "hit_back_faces": {"type": "bool"},
        "exclude_parent": {"type": "bool"},
        "debug_shape_custom_color": {"type": "Color"},
    },
    # --- Navigation ---
    "NavigationRegion2D": {
        "enabled": {"type": "bool"},
        "navigation_polygon": {
            "type": "sub_resource",
            "resource_type": "NavigationPolygon",
        },
        "use_node_rotation": {"type": "bool"},
    },
    "NavigationRegion3D": {
        "enabled": {"type": "bool"},
        "navigation_mesh": {"type": "sub_resource", "resource_type": "NavigationMesh"},
        "use_node_rotation": {"type": "bool"},
    },
    "NavigationAgent2D": {
        "target_position": {"type": "Vector2"},
        "path_desired_distance": {"type": "float"},
        "target_desired_distance": {"type": "float"},
        "max_speed": {"type": "float"},
        "velocity_computed": {"type": "bool"},
        "avoidance_enabled": {"type": "bool"},
        "avoidance_priority": {"type": "float"},
    },
    "NavigationAgent3D": {
        "target_position": {"type": "Vector3"},
        "path_desired_distance": {"type": "float"},
        "target_desired_distance": {"type": "float"},
        "max_speed": {"type": "float"},
        "velocity_computed": {"type": "bool"},
        "avoidance_enabled": {"type": "bool"},
        "avoidance_priority": {"type": "float"},
    },
    # --- TileMap ---
    "TileMap": {
        "tile_set": {"type": "ext_resource", "resource_type": "TileSet"},
        "y_sort_origin": {"type": "int"},
        "collision_layer": {"type": "int"},
        "collision_visibility_mode": {"type": "int"},
        "navigation_layer": {"type": "int"},
        "navigation_visibility_mode": {"type": "int"},
        "rendering_layer": {"type": "int"},
        "rendering_visibility_mode": {"type": "int"},
    },
    "TileMapLayer": {
        "tile_set": {"type": "ext_resource", "resource_type": "TileSet"},
        "y_sort_origin": {"type": "int"},
        "collision_layer": {"type": "int"},
        "navigation_layer": {"type": "int"},
    },
    # --- World ---
    "WorldEnvironment": {
        "environment": {"type": "ext_resource", "resource_type": "Environment"},
        "camera_effects": {"type": "ext_resource", "resource_type": "CameraEffects"},
    },
    "Environment": {
        "background_mode": {
            "type": "int",
            "enum": {
                "BG_CLEAR_COLOR": 0,
                "BG_COLOR": 1,
                "BG_SKY": 2,
                "BG_CUSTOM_SKY": 3,
                "BG_PANORAMA": 4,
                "BG_CANVAS": 5,
                "BG_KEEP": 6,
            },
        },
        "bg_color": {"type": "Color"},
        "sky": {"type": "ext_resource", "resource_type": "Sky"},
        "sky_custom_fov": {"type": "float"},
        "sky_rotation": {"type": "Vector3"},
        "ambient_light_source": {
            "type": "int",
            "enum": {
                "AMBIENT_SOURCE_DISABLED": 0,
                "AMBIENT_SOURCE_COLOR": 1,
                "AMBIENT_SOURCE_SKY": 2,
                "AMBIENT_SOURCE_BG": 3,
            },
        },
        "ambient_light_color": {"type": "Color"},
        "ambient_light_energy": {"type": "float"},
        "fog_enabled": {"type": "bool"},
        "fog_density": {"type": "float"},
        "fog_height_enabled": {"type": "bool"},
        "fog_height_min": {"type": "float"},
        "fog_height_max": {"type": "float"},
        "fog_height_density": {"type": "float"},
        "fog_depth_enabled": {"type": "bool"},
        "fog_depth_begin": {"type": "float"},
        "fog_depth_end": {"type": "float"},
        "fog_depth_curve": {"type": "float"},
        "fog_sun_enabled": {"type": "bool"},
        "fog_sun_amount": {"type": "float"},
        "fog_sun_color": {"type": "Color"},
        "tonemap_mode": {
            "type": "int",
            "enum": {
                "TONEMAPPER_LINEAR": 0,
                "TONEMAPPER_REINHARDT": 1,
                "TONEMAPPER_FILMIC": 2,
                "TONEMAPPER_ACES": 3,
                "TONEMAPPER_ACES2": 4,
            },
        },
        "tonemap_exposure": {"type": "float"},
        "tonemap_white": {"type": "float"},
        "ssr_enabled": {"type": "bool"},
        "ssr_max_steps": {"type": "int"},
        "ssr_fade_in": {"type": "float"},
        "ssr_fade_out": {"type": "float"},
        "ssr_depth_tolerance": {"type": "float"},
        "ssao_enabled": {"type": "bool"},
        "ssao_radius": {"type": "float"},
        "ssao_intensity": {"type": "float"},
        "ssao_power": {"type": "float"},
        "ssao_detail": {"type": "float"},
        "ssao_horizon": {"type": "float"},
        "ssao_sharpness": {"type": "float"},
        "ssil_enabled": {"type": "bool"},
        "ssil_radius": {"type": "float"},
        "ssil_intensity": {"type": "float"},
        "ssil_power": {"type": "float"},
        "ssil_detail": {"type": "float"},
        "ssil_horizon": {"type": "float"},
        "ssil_sharpness": {"type": "float"},
        "sdfgi_enabled": {"type": "bool"},
        "sdfgi_use_occlusion": {"type": "bool"},
        "sdfgi_cascade0_distance": {"type": "float"},
        "sdfgi_cascade0_max_distance": {"type": "float"},
        "sdfgi_cascade_count": {"type": "int"},
        "sdfgi_y_scale": {"type": "int"},
        "sdfgi_min_cell_size": {"type": "float"},
        "sdfgi_max_distance": {"type": "float"},
        "sdfgi_trace_multibounce": {"type": "bool"},
        "sdfgi_bounce_feedback": {"type": "float"},
        "sdfgi_read_sky_light": {"type": "bool"},
        "sdfgi_energy": {"type": "float"},
        "sdfgi_normal_bias": {"type": "float"},
        "sdfgi_distance_fade_enabled": {"type": "bool"},
        "sdfgi_distance_fade_begin": {"type": "float"},
        "sdfgi_distance_fade_length": {"type": "float"},
        "glow_enabled": {"type": "bool"},
        "glow_level_1": {"type": "float"},
        "glow_level_2": {"type": "float"},
        "glow_level_3": {"type": "float"},
        "glow_level_4": {"type": "float"},
        "glow_level_5": {"type": "float"},
        "glow_level_6": {"type": "float"},
        "glow_level_7": {"type": "float"},
        "glow_intensity": {"type": "float"},
        "glow_strength": {"type": "float"},
        "glow_blend_mode": {
            "type": "int",
            "enum": {
                "GLOW_BLEND_MODE_ADDITIVE": 0,
                "GLOW_BLEND_MODE_SCREEN": 1,
                "GLOW_BLEND_MODE_SOFTLIGHT": 2,
                "GLOW_BLEND_MODE_REPLACE": 3,
            },
        },
        "glow_bloom": {"type": "float"},
        "glow_hdr_threshold": {"type": "float"},
        "glow_hdr_scale": {"type": "float"},
        "glow_high_quality": {"type": "bool"},
        "adjustment_enabled": {"type": "bool"},
        "adjustment_brightness": {"type": "float"},
        "adjustment_contrast": {"type": "float"},
        "adjustment_saturation": {"type": "float"},
    },
    # --- Physics Materials ---
    "PhysicsMaterial": {
        "friction": {"type": "float"},
        "bounce": {"type": "float"},
        "rough": {"type": "bool"},
        "absorbent": {"type": "bool"},
    },
    # --- 2D Shapes (SubResources) ---
    "RectangleShape2D": {
        "size": {"type": "Vector2"},
    },
    "CircleShape2D": {
        "radius": {"type": "float"},
    },
    "CapsuleShape2D": {
        "radius": {"type": "float"},
        "height": {"type": "float"},
    },
    "WorldBoundaryShape2D": {
        "line": {"type": "Vector2"},
    },
    "SegmentShape2D": {
        "a": {"type": "Vector2"},
        "b": {"type": "Vector2"},
    },
    "ConvexPolygonShape2D": {
        "points": {"type": "PackedVector2Array"},
    },
    "ConcavePolygonShape2D": {
        "points": {"type": "PackedVector3Array"},
    },
    "RectangleShape3D": {
        "size": {"type": "Vector3"},
    },
    "SphereShape3D": {
        "radius": {"type": "float"},
    },
    "CapsuleShape3D": {
        "radius": {"type": "float"},
        "height": {"type": "float"},
    },
    "CylinderShape3D": {
        "radius": {"type": "float"},
        "height": {"type": "float"},
    },
    "WorldBoundaryShape3D": {
        "plane": {"type": "Plane"},
    },
    "ConvexPolygonShape3D": {
        "points": {"type": "PackedVector3Array"},
    },
    "ConcavePolygonShape3D": {
        "points": {"type": "PackedVector3Array"},
    },
    "BoxShape3D": {
        "size": {"type": "Vector3"},
    },
    # --- Meshes (SubResources) ---
    "BoxMesh": {
        "size": {"type": "Vector3"},
        "subdivide_width": {"type": "int"},
        "subdivide_height": {"type": "int"},
        "subdivide_depth": {"type": "int"},
    },
    "SphereMesh": {
        "radius": {"type": "float"},
        "height": {"type": "float"},
        "radial_segments": {"type": "int"},
        "rings": {"type": "int"},
    },
    "CylinderMesh": {
        "radius": {"type": "float"},
        "height": {"type": "float"},
        "radial_segments": {"type": "int"},
        "rings": {"type": "int"},
    },
    "CapsuleMesh": {
        "radius": {"type": "float"},
        "height": {"type": "float"},
        "radial_segments": {"type": "int"},
        "rings": {"type": "int"},
    },
    "PlaneMesh": {
        "size": {"type": "Vector2"},
        "subdivide_width": {"type": "int"},
        "subdivide_depth": {"type": "int"},
    },
    "QuadMesh": {
        "size": {"type": "Vector2"},
        "subdivide_width": {"type": "int"},
        "subdivide_depth": {"type": "int"},
    },
    "PrismMesh": {
        "size": {"type": "Vector3"},
        "subdivide_width": {"type": "int"},
        "subdivide_height": {"type": "int"},
        "subdivide_depth": {"type": "int"},
    },
    "TorusMesh": {
        "inner_radius": {"type": "float"},
        "outer_radius": {"type": "float"},
        "sides": {"type": "int"},
        "ring_segments": {"type": "int"},
    },
    "RibbonTrailMesh": {
        "length": {"type": "float"},
        "width": {"type": "float"},
        "lifetime": {"type": "float"},
        "lifetime_randomness": {"type": "float"},
    },
    "TubeTrailMesh": {
        "length": {"type": "float"},
        "radius": {"type": "float"},
        "lifetime": {"type": "float"},
        "lifetime_randomness": {"type": "float"},
    },
    # --- Particle Process Material (SubResource) ---
    "ParticleProcessMaterial": {
        "direction": {"type": "Vector3"},
        "spread": {"type": "float"},
        "flatness": {"type": "float"},
        "initial_velocity_min": {"type": "float"},
        "initial_velocity_max": {"type": "float"},
        "angular_velocity_min": {"type": "float"},
        "angular_velocity_max": {"type": "float"},
        "orbit_velocity_min": {"type": "float"},
        "orbit_velocity_max": {"type": "float"},
        "linear_accel_min": {"type": "float"},
        "linear_accel_max": {"type": "float"},
        "radial_accel_min": {"type": "float"},
        "radial_accel_max": {"type": "float"},
        "tangential_accel_min": {"type": "float"},
        "tangential_accel_max": {"type": "float"},
        "damping_min": {"type": "float"},
        "damping_max": {"type": "float"},
        "angle_min": {"type": "float"},
        "angle_max": {"type": "float"},
        "scale_min": {"type": "float"},
        "scale_max": {"type": "float"},
        "hue_variation_min": {"type": "float"},
        "hue_variation_max": {"type": "float"},
        "anim_speed_min": {"type": "float"},
        "anim_speed_max": {"type": "float"},
        "anim_offset_min": {"type": "float"},
        "anim_offset_max": {"type": "float"},
        "emission_shape": {
            "type": "int",
            "enum": {
                "EMISSION_SHAPE_POINT": 0,
                "EMISSION_SHAPE_SPHERE": 1,
                "EMISSION_SHAPE_BOX": 2,
                "EMISSION_SHAPE_POINTS": 3,
                "EMISSION_SHAPE_DIRECTED_POINTS": 4,
                "EMISSION_SHAPE_RING": 5,
                "EMISSION_SHAPE_MAX": 6,
            },
        },
        "emission_sphere_radius": {"type": "float"},
        "emission_box_extents": {"type": "Vector3"},
        "emission_ring_radius": {"type": "float"},
        "emission_ring_height": {"type": "float"},
        "emission_ring_cone_angle": {"type": "float"},
        "gravity": {"type": "Vector3"},
        "color_ramp": {"type": "ext_resource", "resource_type": "GradientTexture1D"},
        "scale_curve_min": {"type": "float"},
        "scale_curve_max": {"type": "float"},
    },
    # --- Path ---
    "Path2D": {
        "curve": {"type": "sub_resource", "resource_type": "Curve2D"},
    },
    "Path3D": {
        "curve": {"type": "sub_resource", "resource_type": "Curve3D"},
    },
    "PathFollow2D": {
        "progress": {"type": "float"},
        "progress_ratio": {"type": "float"},
        "rotates": {"type": "bool"},
        "loop": {"type": "bool"},
        "cubic_interp": {"type": "bool"},
    },
    "PathFollow3D": {
        "progress": {"type": "float"},
        "progress_ratio": {"type": "float"},
        "rotates": {"type": "bool"},
        "loop": {"type": "bool"},
        "cubic_interp": {"type": "bool"},
        "tilt_enabled": {"type": "bool"},
        "tilt_angle": {"type": "float"},
    },
    # --- Visibility ---
    "VisibleOnScreenNotifier2D": {
        "rect": {"type": "Rect2"},
    },
    "VisibleOnScreenNotifier3D": {},
    "VisibilityNotifier2D": {
        "rect": {"type": "Rect2"},
    },
    "VisibilityEnabler2D": {
        "rect": {"type": "Rect2"},
        "freeze_enabled": {"type": "bool"},
        "pause_enabled": {"type": "bool"},
    },
    "VisibilityEnabler3D": {
        "extents": {"type": "Vector3"},
        "freeze_enabled": {"type": "bool"},
        "pause_enabled": {"type": "bool"},
    },
    # --- RemoteTransform ---
    "RemoteTransform2D": {
        "remote_path": {"type": "NodePath"},
        "update_position": {"type": "bool"},
        "update_rotation": {"type": "bool"},
        "update_scale": {"type": "bool"},
        "use_global_coordinates": {"type": "bool"},
    },
    "RemoteTransform3D": {
        "remote_path": {"type": "NodePath"},
        "update_position": {"type": "bool"},
        "update_rotation": {"type": "bool"},
        "update_scale": {"type": "bool"},
        "use_global_coordinates": {"type": "bool"},
    },
    # --- SpringArm ---
    "SpringArm2D": {
        "length": {"type": "float"},
        "collision_mask": {"type": "int"},
        "exclude_parent": {"type": "bool"},
        "shape": {"type": "sub_resource", "resource_type": "Shape2D"},
    },
    "SpringArm3D": {
        "length": {"type": "float"},
        "collision_mask": {"type": "int"},
        "exclude_parent": {"type": "bool"},
        "shape": {"type": "sub_resource", "resource_type": "Shape3D"},
    },
    # --- Skeleton ---
    "Skeleton2D": {},
    "Skeleton3D": {
        "bone_orientation": {"type": "int"},
    },
    "Bone2D": {
        "length": {"type": "float"},
    },
    "BoneAttachment3D": {},
    # --- LightOccluder ---
    "LightOccluder2D": {
        "occluder": {"type": "sub_resource", "resource_type": "OccluderPolygon2D"},
        "sdf_collision": {"type": "bool"},
    },
    "OccluderPolygon2D": {
        "polygon": {"type": "PackedVector2Array"},
        "closed": {"type": "bool"},
        "cull_mode": {
            "type": "int",
            "enum": {
                "OCCLUDER_CULL_DISABLED": 0,
                "OCCLUDER_CULL_CLOCKWISE": 1,
                "OCCLUDER_CULL_COUNTER_CLOCKWISE": 2,
            },
        },
    },
    # --- Curve ---
    "Curve2D": {
        "points": {"type": "PackedVector2Array"},
    },
    "Curve3D": {
        "points": {"type": "PackedVector3Array"},
    },
    # --- Viewport ---
    "SubViewport": {
        "size": {"type": "Vector2i"},
        "world_2d": {"type": "ext_resource", "resource_type": "World2D"},
        "world_3d": {"type": "ext_resource", "resource_type": "World3D"},
        "disable_3d": {"type": "bool"},
        "physics_object_picking": {"type": "bool"},
        "physics_object_picking_first_only": {"type": "bool"},
        "use_own_world": {"type": "bool"},
        "render_target_update_mode": {
            "type": "int",
            "enum": {
                "VIEWPORT_UPDATE_DISABLED": 0,
                "VIEWPORT_UPDATE_ONCE": 1,
                "VIEWPORT_UPDATE_WHEN_VISIBLE": 2,
                "VIEWPORT_UPDATE_ALWAYS": 3,
            },
        },
        "render_target_clear_mode": {
            "type": "int",
            "enum": {
                "VIEWPORT_CLEAR_ALWAYS": 0,
                "VIEWPORT_CLEAR_NEVER": 1,
                "VIEWPORT_CLEAR_ONLY_NEXT_FRAME": 2,
            },
        },
        "transparent_bg": {"type": "bool"},
        "vflip": {"type": "bool"},
        "keep_3d_linear": {"type": "bool"},
        "msaa_2d": {
            "type": "int",
            "enum": {
                "MSAA_DISABLED": 0,
                "MSAA_2X": 1,
                "MSAA_4X": 2,
                "MSAA_8X": 3,
                "MSAA_16X": 4,
            },
        },
        "msaa_3d": {
            "type": "int",
            "enum": {
                "MSAA_DISABLED": 0,
                "MSAA_2X": 1,
                "MSAA_4X": 2,
                "MSAA_8X": 3,
                "MSAA_16X": 4,
            },
        },
        "audio_listener_enable_2d": {"type": "bool"},
        "audio_listener_enable_3d": {"type": "bool"},
    },
    "SubViewportContainer": {
        "stretch": {"type": "bool"},
        "stretch_shrink": {"type": "int"},
        "follow_viewport_enabled": {"type": "bool"},
    },
    # --- CanvasLayer ---
    "CanvasLayer": {
        "layer": {"type": "int"},
        "offset": {"type": "Vector2"},
        "rotation": {"type": "float"},
        "scale": {"type": "Vector2"},
    },
    # --- YSort ---
    "YSort": {
        "y_sort_enabled": {"type": "bool"},
        "y_sort_origin": {"type": "int"},
    },
    # --- Parallax ---
    "ParallaxBackground": {
        "scroll_base_offset": {"type": "Vector2"},
        "scroll_base_scale": {"type": "Vector2"},
        "scroll_ignore_camera_zoom": {"type": "bool"},
    },
    "ParallaxLayer": {
        "motion_mirroring": {"type": "Vector2"},
        "motion_scale": {"type": "Vector2"},
        "motion_offset": {"type": "Vector2"},
    },
    # --- Materials ---
    "ShaderMaterial": {
        "shader": {"type": "ext_resource", "resource_type": "Shader"},
    },
    "StandardMaterial3D": {
        "albedo_color": {"type": "Color"},
        "albedo_texture": {"type": "ext_resource", "resource_type": "Texture2D"},
        "metallic": {"type": "float"},
        "metallic_texture": {"type": "ext_resource", "resource_type": "Texture2D"},
        "roughness": {"type": "float"},
        "roughness_texture": {"type": "ext_resource", "resource_type": "Texture2D"},
        "emission": {"type": "Color"},
        "emission_texture": {"type": "ext_resource", "resource_type": "Texture2D"},
        "emission_energy_multiplier": {"type": "float"},
        "normal_enabled": {"type": "bool"},
        "normal_texture": {"type": "ext_resource", "resource_type": "Texture2D"},
        "normal_scale": {"type": "float"},
        "rim_enabled": {"type": "bool"},
        "rim": {"type": "Color"},
        "rim_force_r0": {"type": "float"},
        "clearcoat_enabled": {"type": "bool"},
        "clearcoat": {"type": "float"},
        "clearcoat_roughness": {"type": "float"},
        "anisotropy_enabled": {"type": "bool"},
        "anisotropy": {"type": "float"},
        "anisotropy_flowmap": {"type": "ext_resource", "resource_type": "Texture2D"},
        "heightmap_enabled": {"type": "bool"},
        "heightmap_texture": {"type": "ext_resource", "resource_type": "Texture2D"},
        "heightmap_min_layers": {"type": "int"},
        "heightmap_max_layers": {"type": "int"},
        "heightmap_flip": {"type": "Vector2"},
        "subsurf_scatter_enabled": {"type": "bool"},
        "subsurf_scatter_strength": {"type": "float"},
        "transmission_enabled": {"type": "bool"},
        "transmission": {"type": "float"},
        "transmission_color": {"type": "Color"},
        "transmission_color_texture": {
            "type": "ext_resource",
            "resource_type": "Texture2D",
        },
        "transmission_color_depth": {"type": "float"},
        "transmission_color_distance": {"type": "float"},
        "refraction_enabled": {"type": "bool"},
        "refraction": {"type": "float"},
        "refraction_texture": {"type": "ext_resource", "resource_type": "Texture2D"},
        "refraction_scale": {"type": "float"},
        "detail_enabled": {"type": "bool"},
        "detail_albedo": {"type": "ext_resource", "resource_type": "Texture2D"},
        "detail_normal": {"type": "ext_resource", "resource_type": "Texture2D"},
        "detail_blend_mode": {"type": "int"},
        "ao_enabled": {"type": "bool"},
        "ao_texture": {"type": "ext_resource", "resource_type": "Texture2D"},
        "ao_light_affect": {"type": "float"},
        "uv1_scale": {"type": "Vector3"},
        "uv1_offset": {"type": "Vector3"},
        "uv2_scale": {"type": "Vector3"},
        "uv2_offset": {"type": "Vector3"},
        "uv1_blend_sharpness": {"type": "float"},
        "uv2_blend_sharpness": {"type": "float"},
        "particles_anim_h_frames": {"type": "int"},
        "particles_anim_v_frames": {"type": "int"},
        "particles_anim_loop": {"type": "bool"},
        "heightmap_deep_parallax": {"type": "bool"},
        "bloom_enabled": {"type": "bool"},
        "bloom_intensity": {"type": "float"},
        "shading_mode": {
            "type": "int",
            "enum": {"SHADING_MODE_PER_PIXEL": 0, "SHADING_MODE_PER_VERTEX": 1},
        },
        "cull_mode": {
            "type": "int",
            "enum": {"CULL_BACK": 0, "CULL_FRONT": 1, "CULL_DISABLED": 2},
        },
        "diffuse_mode": {
            "type": "int",
            "enum": {
                "DIFFUSE_BURLEY": 0,
                "DIFFUSE_LAMBERT": 1,
                "DIFFUSE_LAMBERT_WRAP": 2,
                "DIFFUSE_TOON": 3,
            },
        },
        "specular_mode": {
            "type": "int",
            "enum": {
                "SPECULAR_SCHLICK_GGX": 0,
                "SPECULAR_TOON": 1,
                "SPECULAR_DISABLED": 2,
            },
        },
        "blend_mode": {
            "type": "int",
            "enum": {
                "BLEND_MODE_MIX": 0,
                "BLEND_MODE_ADD": 1,
                "BLEND_MODE_SUB": 2,
                "BLEND_MODE_MUL": 3,
            },
        },
        "depth_draw_mode": {
            "type": "int",
            "enum": {
                "DEPTH_DRAW_OPAQUE_ONLY": 0,
                "DEPTH_DRAW_ALWAYS": 1,
                "DEPTH_DRAW_DISABLED": 2,
            },
        },
        "texture_filter": {
            "type": "int",
            "enum": {
                "TEXTURE_FILTER_NEAREST": 0,
                "TEXTURE_FILTER_LINEAR": 1,
                "TEXTURE_FILTER_NEAREST_WITH_MIPMAPS": 2,
                "TEXTURE_FILTER_LINEAR_WITH_MIPMAPS": 3,
                "TEXTURE_FILTER_NEAREST_WITH_MIPMAPS_ANISOTROPIC": 4,
                "TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC": 5,
            },
        },
        "texture_repeat": {
            "type": "int",
            "enum": {
                "TEXTURE_REPEAT_ENABLED": 0,
                "TEXTURE_REPEAT_DISABLED": 1,
                "TEXTURE_REPEAT_MIRROR": 2,
            },
        },
        "grow_enabled": {"type": "bool"},
        "grow": {"type": "float"},
        "alpha_antialiasing_mode": {
            "type": "int",
            "enum": {
                "ALPHA_ANTIALIASING_OFF": 0,
                "ALPHA_ANTIALIASING_ALPHA_DITHER": 1,
                "ALPHA_ANTIALIASING_ALPHA_TO_COVERAGE": 2,
            },
        },
        "alpha_scissor_threshold": {"type": "float"},
        "alpha_hash_scale": {"type": "float"},
        "alpha_edge_feathering": {"type": "float"},
        "ao_on_uv2": {"type": "bool"},
        "vertex_color_is_srgb": {"type": "bool"},
    },
    "ORMMaterial3D": {
        "albedo_color": {"type": "Color"},
        "albedo_texture": {"type": "ext_resource", "resource_type": "Texture2D"},
        "metallic": {"type": "float"},
        "roughness": {"type": "float"},
        "emission": {"type": "Color"},
        "emission_texture": {"type": "ext_resource", "resource_type": "Texture2D"},
        "normal_enabled": {"type": "bool"},
        "normal_texture": {"type": "ext_resource", "resource_type": "Texture2D"},
        "normal_scale": {"type": "float"},
        "ao_texture": {"type": "ext_resource", "resource_type": "Texture2D"},
        "ao_light_affect": {"type": "float"},
        "cull_mode": {
            "type": "int",
            "enum": {"CULL_BACK": 0, "CULL_FRONT": 1, "CULL_DISABLED": 2},
        },
        "blend_mode": {
            "type": "int",
            "enum": {
                "BLEND_MODE_MIX": 0,
                "BLEND_MODE_ADD": 1,
                "BLEND_MODE_SUB": 2,
                "BLEND_MODE_MUL": 3,
            },
        },
        "depth_draw_mode": {
            "type": "int",
            "enum": {
                "DEPTH_DRAW_OPAQUE_ONLY": 0,
                "DEPTH_DRAW_ALWAYS": 1,
                "DEPTH_DRAW_DISABLED": 2,
            },
        },
        "texture_filter": {"type": "int"},
        "texture_repeat": {"type": "int"},
    },
    # --- Sky ---
    "ProceduralSkyMaterial": {
        "sky_top_color": {"type": "Color"},
        "sky_horizon_color": {"type": "Color"},
        "sky_curve": {"type": "float"},
        "sky_blend": {"type": "float"},
        "sun_enabled": {"type": "bool"},
        "sun_azimuth": {"type": "float"},
        "sun_altitude": {"type": "float"},
        "sun_energy": {"type": "float"},
        "sun_scale": {"type": "float"},
        "sun_color": {"type": "Color"},
        "sun_curve": {"type": "float"},
        "sun_blend": {"type": "float"},
        "ground_color": {"type": "Color"},
        "ground_curve": {"type": "float"},
        "ground_blend": {"type": "float"},
        "ground_horizon_color": {"type": "Color"},
    },
    "PanoramaSkyMaterial": {
        "panorama": {"type": "ext_resource", "resource_type": "Texture2D"},
        "energy": {"type": "float"},
    },
    "PhysicalSkyMaterial": {
        "sky_top_color": {"type": "Color"},
        "sky_horizon_color": {"type": "Color"},
        "sky_curve": {"type": "float"},
        "sky_blend": {"type": "float"},
        "sun_azimuth": {"type": "float"},
        "sun_altitude": {"type": "float"},
        "sun_energy": {"type": "float"},
        "sun_scale": {"type": "float"},
        "sun_color": {"type": "Color"},
        "sun_curve": {"type": "float"},
        "sun_blend": {"type": "float"},
        "ground_color": {"type": "Color"},
        "ground_curve": {"type": "float"},
        "ground_blend": {"type": "float"},
        "ground_horizon_color": {"type": "Color"},
        "turbidity": {"type": "float"},
        "ground_albedo": {"type": "float"},
    },
    # --- Multiplayer ---
    "MultiplayerSpawner": {
        "spawn_path": {"type": "NodePath"},
        "auto_spawn": {"type": "bool"},
    },
    # --- Joints 2D ---
    "PinJoint2D": {
        "node_a": {"type": "NodePath"},
        "node_b": {"type": "NodePath"},
        "bias": {"type": "float"},
        "softness": {"type": "float"},
    },
    "DampedSpringJoint2D": {
        "node_a": {"type": "NodePath"},
        "node_b": {"type": "NodePath"},
        "rest_length": {"type": "float"},
        "stiffness": {"type": "float"},
        "damping": {"type": "float"},
    },
    "GrooveJoint2D": {
        "node_a": {"type": "NodePath"},
        "node_b": {"type": "NodePath"},
        "groove_a1": {"type": "Vector2"},
        "groove_a2": {"type": "Vector2"},
        "anchor_b": {"type": "Vector2"},
    },
    # --- Joints 3D ---
    "HingeJoint3D": {
        "node_a": {"type": "NodePath"},
        "node_b": {"type": "NodePath"},
        "bias": {"type": "float"},
        "softness": {"type": "float"},
    },
    "SliderJoint3D": {
        "node_a": {"type": "NodePath"},
        "node_b": {"type": "NodePath"},
    },
    "ConeTwistJoint3D": {
        "node_a": {"type": "NodePath"},
        "node_b": {"type": "NodePath"},
    },
    "Generic6DOFJoint3D": {
        "node_a": {"type": "NodePath"},
        "node_b": {"type": "NodePath"},
    },
    # --- Visibility ---
    "VisibleOnScreenNotifier2D": {
        "rect": {"type": "Rect2"},
    },
    "VisibleOnScreenNotifier3D": {},
    # --- ShapeCast ---
    "ShapeCast2D": {
        "target_position": {"type": "Vector2"},
        "enabled": {"type": "bool"},
        "collision_mask": {"type": "int"},
        "shape": {"type": "sub_resource", "resource_type": "Shape2D"},
    },
    "ShapeCast3D": {
        "target_position": {"type": "Vector3"},
        "enabled": {"type": "bool"},
        "collision_mask": {"type": "int"},
        "shape": {"type": "sub_resource", "resource_type": "Shape3D"},
    },
    # --- Vehicle ---
    "VehicleBody2D": {
        "engine_force": {"type": "float"},
        "brake": {"type": "float"},
        "steering": {"type": "float"},
    },
    "VehicleWheel2D": {
        "radius": {"type": "float"},
        "friction": {"type": "float"},
        "suspension_stiffness": {"type": "float"},
        "suspension_damping": {"type": "float"},
    },
    "VehicleBody3D": {
        "engine_force": {"type": "float"},
        "brake": {"type": "float"},
        "steering": {"type": "float"},
    },
    "VehicleWheel3D": {
        "radius": {"type": "float"},
        "friction": {"type": "float"},
        "suspension_stiffness": {"type": "float"},
        "suspension_damping": {"type": "float"},
    },
    # --- AnimatableBody ---
    "AnimatableBody2D": {
        "sync_to_physics": {"type": "bool"},
    },
    "AnimatableBody3D": {
        "sync_to_physics": {"type": "bool"},
    },
    # --- Marker ---
    "Marker2D": {},
    "Marker3D": {},
    # --- Node base types ---
    "Node": {},
    "Node2D": {},
    "Node3D": {},
    "Control": {
        "mouse_filter": {
            "type": "int",
            "enum": {
                "MOUSE_FILTER_STOP": 0,
                "MOUSE_FILTER_PASS": 1,
                "MOUSE_FILTER_IGNORE": 2,
            },
        },
        "focus_mode": {
            "type": "int",
            "enum": {
                "FOCUS_NONE": 0,
                "FOCUS_CLICK": 1,
                "FOCUS_ALL": 2,
                "FOCUS_ACCESSIBILITY": 3,
            },
        },
        "clip_contents": {"type": "bool"},
        "anchors_preset": {"type": "int"},
        "anchor_left": {"type": "float"},
        "anchor_right": {"type": "float"},
        "anchor_top": {"type": "float"},
        "anchor_bottom": {"type": "float"},
        "offset_left": {"type": "float"},
        "offset_right": {"type": "float"},
        "offset_top": {"type": "float"},
        "offset_bottom": {"type": "float"},
        "grow_horizontal": {
            "type": "int",
            "enum": {
                "GROW_DIRECTION_BEGIN": 0,
                "GROW_DIRECTION_END": 1,
                "GROW_DIRECTION_BOTH": 2,
            },
        },
        "grow_vertical": {
            "type": "int",
            "enum": {
                "GROW_DIRECTION_BEGIN": 0,
                "GROW_DIRECTION_END": 1,
                "GROW_DIRECTION_BOTH": 2,
            },
        },
    },
}

# Shape type mapping: maps shape property names to concrete shape types
SHAPE_TYPE_MAP: dict[str, str] = {
    "shape": "Shape2D",  # Will be overridden based on parent node type
}

# Shape2D concrete types
SHAPE_2D_TYPES = {
    "RectangleShape2D",
    "CircleShape2D",
    "CapsuleShape2D",
    "WorldBoundaryShape2D",
    "SegmentShape2D",
    "ConvexPolygonShape2D",
    "ConcavePolygonShape2D",
}

# Shape3D concrete types
SHAPE_3D_TYPES = {
    "RectangleShape3D",
    "SphereShape3D",
    "CapsuleShape3D",
    "CylinderShape3D",
    "WorldBoundaryShape3D",
    "BoxShape3D",
    "ConvexPolygonShape3D",
    "ConcavePolygonShape3D",
}

# Node types that use Shape2D
SHAPE_2D_NODES = {
    "CollisionShape2D",
    "CollisionPolygon2D",
    "RayCast2D",
    "ShapeCast2D",
    "Area2D",
    "StaticBody2D",
    "RigidBody2D",
    "CharacterBody2D",
    "PhysicsBody2D",
    "AnimatableBody2D",
    "LightOccluder2D",
    "VisibilityNotifier2D",
    "VisibleOnScreenNotifier2D",
    "SpringArm2D",
    "VehicleBody2D",
    "VehicleWheel2D",
    "NavigationRegion2D",
    "NavigationAgent2D",
    "NavigationObstacle2D",
}

# Node types that use Shape3D
SHAPE_3D_NODES = {
    "CollisionShape3D",
    "CollisionPolygon3D",
    "RayCast3D",
    "ShapeCast3D",
    "Area3D",
    "StaticBody3D",
    "RigidBody3D",
    "CharacterBody3D",
    "PhysicsBody3D",
    "AnimatableBody3D",
    "VisibilityNotifier3D",
    "VisibleOnScreenNotifier3D",
    "SpringArm3D",
    "VehicleBody3D",
    "VehicleWheel3D",
    "NavigationRegion3D",
    "NavigationAgent3D",
    "NavigationObstacle3D",
}


def _get_shape_resource_type(node_type: str) -> str:
    """Determine if a node uses Shape2D or Shape3D."""
    if node_type in SHAPE_2D_NODES:
        return "Shape2D"
    elif node_type in SHAPE_3D_NODES:
        return "Shape3D"
    return "Shape2D"  # Default to 2D


def _resolve_shape_type(value: Any, node_type: str) -> str:
    """Resolve the concrete shape type from a property value."""
    if isinstance(value, dict):
        # If user specified a concrete shape type
        if "shape_type" in value:
            return value["shape_type"]
        # If the value itself has a "type" key that's a shape type
        if "type" in value and value["type"] in (SHAPE_2D_TYPES | SHAPE_3D_TYPES):
            return value["type"]
    # Default based on node type
    return _get_shape_resource_type(node_type)


def _process_property_value(
    scene: Scene,
    node: SceneNode,
    key: str,
    value: Any,
    schema: dict | None = None,
) -> tuple[Any, list[str]]:
    """
    Process a single property value, creating resources as needed.

    Returns: (processed_value, messages)
    """
    messages = []

    # Case 1: Value is a string starting with "res://" -> create ExtResource
    if isinstance(value, str) and value.startswith("res://"):
        resource_type = "Resource"
        if schema and "resource_type" in schema:
            resource_type = schema["resource_type"]

        # Check if already exists
        for ext in scene.ext_resources:
            if ext.path == value:
                clean_id = _clean_resource_id(ext.id)
                return f'ExtResource("{clean_id}")', messages

        # Create new ExtResource
        ext_id = str(len(scene.ext_resources) + 1)
        new_ext = ExtResource(type=resource_type, path=value, id=ext_id)
        scene.ext_resources.append(new_ext)
        messages.append(f"Created ExtResource '{resource_type}' -> {value}")
        return f'ExtResource("{ext_id}")', messages

    # Case 2: Value is a dict with "type" -> could be resource reference or sub_resource
    if isinstance(value, dict) and "type" in value:
        prop_type = value["type"]

        # Sub-case 2a: Explicit resource reference {"type": "SubResource", "ref": "id"}
        if prop_type == "SubResource" and "ref" in value:
            ref_id = _clean_resource_id(value["ref"])
            return f'SubResource("{ref_id}")', messages

        if prop_type == "ExtResource" and "ref" in value:
            ref_id = _clean_resource_id(value["ref"])
            return f'ExtResource("{ref_id}")', messages

        if prop_type == "NodePath" and "ref" in value:
            return f'NodePath("{value["ref"]}")', messages

        # Sub-case 2b: Typed value like Vector2, Color, Rect2
        typed_values = {
            "Vector2",
            "Vector2i",
            "Vector3",
            "Vector3i",
            "Vector4",
            "Vector4i",
            "Color",
            "Rect2",
            "Rect2i",
            "AABB",
            "Transform2D",
            "Transform3D",
            "Plane",
            "Quaternion",
            "Basis",
            "Projection",
            "PackedVector2Array",
            "PackedVector3Array",
            "PackedVector4Array",
            "PackedColorArray",
            "PackedStringArray",
            "PackedFloat32Array",
            "PackedFloat64Array",
            "PackedInt32Array",
            "PackedInt64Array",
            "PackedByteArray",
            "NodePath",
        }
        if prop_type in typed_values:
            # Store as-is, serialization handles it
            return value, messages

        # Sub-case 2c: Shape definition -> create SubResource
        # A shape dict has properties like {"size": {"type": "Vector2", ...}}
        # or {"radius": 16.0}
        is_shape_def = False
        shape_type = _resolve_shape_type(value, node.type)

        # Check if this looks like a shape definition (has shape properties but no "type" = "SubResource")
        shape_props = {k: v for k, v in value.items() if k != "type"}
        if shape_props and prop_type not in typed_values:
            is_shape_def = True

        if is_shape_def:
            # Use the shape_type from the dict or default
            if "shape_type" in value:
                shape_type = value["shape_type"]
            elif prop_type in (SHAPE_2D_TYPES | SHAPE_3D_TYPES):
                shape_type = prop_type

            sub_id = f"{shape_type}_{_generate_resource_id()}"
            new_sub = SubResource(type=shape_type, id=sub_id, properties=shape_props)
            scene.sub_resources.append(new_sub)
            messages.append(f"Created SubResource '{shape_type}' -> {sub_id}")
            return f'SubResource("{sub_id}")', messages

        # Sub-case 2d: Generic sub_resource definition
        if schema and schema.get("type") == "sub_resource":
            sub_type = schema.get("resource_type", prop_type)
            sub_props = {k: v for k, v in value.items() if k != "type"}
            sub_id = f"{sub_type}_{_generate_resource_id()}"
            new_sub = SubResource(type=sub_type, id=sub_id, properties=sub_props)
            scene.sub_resources.append(new_sub)
            messages.append(f"Created SubResource '{sub_type}' -> {sub_id}")
            return f'SubResource("{sub_id}")', messages

    # Case 3: Value is a dict that looks like a shape definition (no "type" key)
    if isinstance(value, dict) and "type" not in value:
        # Check if this property expects a sub_resource
        if schema and schema.get("type") in ("sub_resource", "resource"):
            shape_type = schema.get("resource_type", "Shape2D")
            # If shape_type is generic (Shape2D/Shape3D), try to infer concrete type
            if shape_type in ("Shape2D", "Shape3D"):
                # Check if value has a shape_type hint
                if "shape_type" in value:
                    shape_type = value["shape_type"]
                else:
                    # Default to first available shape of that dimension
                    shape_type = (
                        "RectangleShape2D" if shape_type == "Shape2D" else "BoxShape3D"
                    )

            sub_id = f"{shape_type}_{_generate_resource_id()}"
            new_sub = SubResource(type=shape_type, id=sub_id, properties=value)
            scene.sub_resources.append(new_sub)
            messages.append(f"Created SubResource '{shape_type}' -> {sub_id}")
            return f'SubResource("{sub_id}")', messages

    # Case 4: Normal value (string, number, bool, etc.)
    return value, messages


def _validate_properties(
    node_type: str,
    properties: dict,
    schema: dict | None = None,
) -> tuple[bool, list[str]]:
    """
    Validate properties against the node's schema.

    Returns: (is_valid, error_messages)
    """
    errors = []

    if not schema:
        # No schema for this node type - allow any properties
        return True, errors

    for key, value in properties.items():
        if key not in schema:
            # Property not in schema - allow it (Godot accepts unknown properties)
            # But warn the user
            continue

        prop_schema = schema[key]
        expected_type = prop_schema.get("type", "any")

        # Validate enum values
        if "enum" in prop_schema and isinstance(value, str):
            if value not in prop_schema["enum"]:
                valid_values = list(prop_schema["enum"].keys())
                errors.append(
                    f"Property '{key}': invalid enum value '{value}'. "
                    f"Valid values: {valid_values}"
                )

    return len(errors) == 0, errors


@require_session
def set_node_properties(
    session_id: str,
    scene_path: str,
    node_path: str,
    properties: dict[str, Any],
) -> dict:
    """
    Set properties on a node in one step. Unified inspector tool.

    This tool handles ALL property types automatically:
    - Simple values (strings, numbers, bools)
    - Typed values (Vector2, Color, Rect2, etc.) via {"type": "Vector2", "x": 10, "y": 20}
    - File paths (res://...) -> auto-creates ExtResource
    - Shape definitions -> auto-creates SubResource
    - Resource references -> {"type": "SubResource", "ref": "id"}

    Args:
        session_id: Session ID from start_session.
        scene_path: Path to the .tscn file.
        node_path: Path or name of the node to update.
        properties: Dict of properties to set.

    Returns:
        Dict with success status, updated properties, and any messages.

    Examples:
        # Set texture from file path
        set_node_properties(scene_path="game.tscn", node_path="Sprite2D",
            properties={"texture": "res://sprites/player.png"})

        # Set shape with SubResource (auto-created)
        set_node_properties(scene_path="game.tscn", node_path="CollisionShape2D",
            properties={"shape": {"size": {"type": "Vector2", "x": 32, "y": 32}}})

        # Set shape with explicit shape type
        set_node_properties(scene_path="game.tscn", node_path="CollisionShape2D",
            properties={"shape": {"shape_type": "CircleShape2D", "radius": 16.0}})

        # Set simple properties
        set_node_properties(scene_path="game.tscn", node_path="Label",
            properties={"text": "Hello World", "visible": true})

        # Set typed values
        set_node_properties(scene_path="game.tscn", node_path="Sprite2D",
            properties={"position": {"type": "Vector2", "x": 100, "y": 200}})

        # Set color
        set_node_properties(scene_path="game.tscn", node_path="Sprite2D",
            properties={"modulate": {"type": "Color", "r": 1.0, "g": 0.5, "b": 0.5, "a": 1.0}})
    """
    scene_path = _ensure_tscn_path(scene_path)

    if not os.path.exists(scene_path):
        return {"success": False, "error": "Scene file not found"}

    scene = parse_tscn(scene_path)

    # Find the node
    result = _find_node_by_path(scene, node_path)
    if not result:
        return {
            "success": False,
            "error": f"Node not found: '{node_path}'",
            "hint": "Use find_nodes to list available nodes",
        }

    idx, node = result

    # Get schema for this node type
    schema = NODE_PROPERTY_SCHEMAS.get(node.type)

    # Validate properties
    is_valid, errors = _validate_properties(node.type, properties, schema)
    if not is_valid:
        return {
            "success": False,
            "error": f"Validation failed: {'; '.join(errors)}",
            "hint": "Check property names and enum values",
        }

    # Process each property
    messages = []
    processed_props = {}

    for key, value in properties.items():
        prop_schema = schema.get(key) if schema else None
        processed, prop_messages = _process_property_value(
            scene, node, key, value, prop_schema
        )
        processed_props[key] = processed
        messages.extend(prop_messages)

    # Update node properties
    old_props = node.properties.copy()
    node.properties.update(processed_props)

    # Update load_steps
    scene.header.load_steps = 1 + len(scene.ext_resources) + len(scene.sub_resources)

    # Save
    _update_scene_file(scene_path, scene)

    return {
        "success": True,
        "message": f"Updated {len(processed_props)} properties on node '{node.name}'",
        "node": node.name,
        "node_type": node.type,
        "properties_set": list(processed_props.keys()),
        "old_properties": old_props,
        "new_properties": node.properties,
        "messages": messages,
        "scene_path": scene_path,
    }


# ============ REGISTRATION ============


def register_property_tools(mcp) -> None:
    """
    Register all property tools.

    Args:
        mcp: FastMCP instance to register tools on.
    """
    logger.info("Registrando property tools...")

    mcp.add_tool(set_node_properties)

    logger.info("[OK] 1 property tool registrada")
