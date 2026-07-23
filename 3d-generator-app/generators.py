from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any

import ezdxf
from build123d import (
    Box, Cylinder, Compound, Part, Pos, Rotation, Solid,
    export_stl, export_step
)

CAD_PYTHON = "/home/x0ttta6bl4/.codex/skills/cad/.venv/bin/python"

# --- 1. АДАПТЕР ДЛЯ ПЫЛЕСОСОВ И ИНСТРУМЕНТА (3D-печать) ---
def generate_adapter(
    d1_outer: float = 35.0,
    d2_outer: float = 32.0,
    length: float = 75.0,
    wall_thickness: float = 2.5,
    output_dir: Path = Path("/tmp")
) -> Dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stl_path = output_dir / "adapter.stl"
    step_path = output_dir / "adapter.step"

    h_sec = length / 3.0
    r1_out = d1_outer / 2.0
    r2_out = d2_outer / 2.0
    r1_in = max(0.5, r1_out - wall_thickness)
    r2_in = max(0.5, r2_out - wall_thickness)

    # Точный параметрический переходник
    outer_bottom = Cylinder(radius=r1_out, height=h_sec)
    outer_top = Pos(0, 0, h_sec * 2) * Cylinder(radius=r2_out, height=h_sec)
    outer_mid = Pos(0, 0, h_sec) * Cylinder(radius=max(r1_out, r2_out), height=h_sec)
    
    # Канал вычитания
    inner_bottom = Cylinder(radius=r1_in, height=h_sec + 2)
    inner_top = Pos(0, 0, h_sec * 2) * Cylinder(radius=r2_in, height=h_sec + 2)
    inner_mid = Pos(0, 0, h_sec) * Cylinder(radius=max(r1_in, r2_in), height=h_sec + 2)

    # Устойчивая геометрия без нависаний
    outer = outer_bottom + outer_top + outer_mid
    inner = inner_bottom + inner_top + inner_mid
    body = outer - inner

    export_stl(body, str(stl_path))
    export_step(body, str(step_path))

    return {"stl": str(stl_path), "step": str(step_path)}


# --- 2. ЯЩИК ИЗ ФАНЕРЫ С DOGBONE И СНИМКОМ DXF (ЧПУ) ---
def generate_plywood_box(
    length: float = 200.0,
    width: float = 140.0,
    height: float = 90.0,
    plywood_thickness: float = 6.0,
    tool_diameter: float = 3.175,
    output_dir: Path = Path("/tmp")
) -> Dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stl_path = output_dir / "plywood_box.stl"
    step_path = output_dir / "plywood_box.step"
    dxf_path = output_dir / "plywood_box_flatpack.dxf"

    t = plywood_thickness

    # 3D Модель ящика
    bottom = Box(length, width, t)
    side_l = Pos(-length/2 + t/2, 0, height/2) * Box(t, width, height)
    side_r = Pos(length/2 - t/2, 0, height/2) * Box(t, width, height)
    front = Pos(0, -width/2 + t/2, height/2) * Box(length - 2*t, t, height)
    back = Pos(0, width/2 - t/2, height/2) * Box(length - 2*t, t, height)

    assembly = Compound(children=[bottom, side_l, side_r, front, back])
    export_stl(assembly, str(stl_path))
    export_step(assembly, str(step_path))

    # 2D DXF Раскрой
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()

    doc.layers.add("CUT_OUTER", color=1)
    doc.layers.add("DOGBONES", color=5)
    doc.layers.add("LABELS", color=7)

    # 1. Дно
    msp.add_lwpolyline([(0, 0), (length, 0), (length, width), (0, width), (0, 0)], dxfattribs={"layer": "CUT_OUTER"})
    msp.add_text("BOTTOM", dxfattribs={"layer": "LABELS", "height": 8}).set_placement((length/3, width/2))

    # Dogbones
    r = tool_diameter / 2.0 + 0.1
    offset = r * math.sqrt(2) / 2
    for cx, cy in [(t, t), (length - t, t), (length - t, width - t), (t, width - t)]:
        msp.add_circle((cx - offset, cy - offset), radius=r, dxfattribs={"layer": "DOGBONES"})

    # 2. Боковины на чертеже раскроя
    gap = 20.0
    y_offset = width + gap
    msp.add_lwpolyline([(0, y_offset), (length, y_offset), (length, y_offset + height), (0, y_offset + height), (0, y_offset)], dxfattribs={"layer": "CUT_OUTER"})
    msp.add_text("SIDE_1", dxfattribs={"layer": "LABELS", "height": 8}).set_placement((length/3, y_offset + height/2))

    doc.saveas(str(dxf_path))

    return {"stl": str(stl_path), "step": str(step_path), "dxf": str(dxf_path)}


# --- 3. ОРГАНИЗАЦИОННЫЙ ЛОТОК GRIDFINITY (3D-печать) ---
def generate_gridfinity(
    grid_x: int = 2,
    grid_y: int = 1,
    unit_height: int = 3, # Units of 7mm (e.g. 3 = 21mm)
    wall_thickness: float = 2.0,
    output_dir: Path = Path("/tmp")
) -> Dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stl_path = output_dir / "gridfinity_bin.stl"
    step_path = output_dir / "gridfinity_bin.step"

    unit_size = 42.0 # Standard Gridfinity 42mm x 42mm
    height_mm = unit_height * 7.0 + 4.4 # Standard height formula

    total_w = grid_x * unit_size
    total_l = grid_y * unit_size

    # Наружный блок
    outer_box = Box(total_w, total_l, height_mm)
    
    # Внутренняя выемка
    inner_w = max(1.0, total_w - wall_thickness * 2)
    inner_l = max(1.0, total_l - wall_thickness * 2)
    inner_h = height_mm - 3.0 # Сплошное донышко 3мм

    inner_box = Pos(0, 0, 1.5) * Box(inner_w, inner_l, inner_h)
    bin_shape = outer_box - inner_box

    export_stl(bin_shape, str(stl_path))
    export_step(bin_shape, str(step_path))

    return {"stl": str(stl_path), "step": str(step_path)}
