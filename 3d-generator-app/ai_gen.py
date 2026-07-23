"""AI 3D Generator — генерация build123d кода из описания + exec + export."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import textwrap
import traceback
import uuid
from pathlib import Path
from typing import Dict, Any, Optional

try:
    import httpx
except ImportError:
    httpx = None

CAD_PYTHON = "/home/x0ttta6bl4/.codex/skills/cad/.venv/bin/python"
OUTPUT_DIR = Path("/mnt/projects/3d-generator-app/output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:1.5b")

EXECUTOR_TEMPLATE = textwrap.dedent("""\
import sys
import json
import traceback
import math
from pathlib import Path

output_dir = Path(sys.argv[1])
model_id = sys.argv[2]
export_fmt = sys.argv[3] if len(sys.argv) > 3 else "both"

try:
    from build123d import *
    from build123d import export_stl, export_step, Compound

    # --- USER CODE START ---
{code}
    # --- USER CODE END ---

    if 'result' not in dir():
        result = locals().get('shape') or locals().get('part') or locals().get('model')

    if result is None:
        print(json.dumps({{"error": "No shape/part/model variable found. Assign your result to 'shape', 'part', or 'model'."}}))
        sys.exit(1)

    stl_path = output_dir / f"{{model_id}}.stl"
    step_path = output_dir / f"{{model_id}}.step"

    if export_fmt in ("stl", "both"):
        export_stl(result, str(stl_path))
    if export_fmt in ("step", "both"):
        export_step(result, str(step_path))

    files = {{}}
    if export_fmt in ("stl", "both"):
        files["stl"] = str(stl_path)
    if export_fmt in ("step", "both"):
        files["step"] = str(step_path)

    print(json.dumps({{"status": "success", "files": files}}))

except Exception as e:
    tb = traceback.format_exc()
    print(json.dumps({{"error": str(e), "traceback": tb}}))
    sys.exit(1)
""")


def run_build123d_code(code: str, export_fmt: str = "both") -> Dict[str, Any]:
    """Execute build123d code and return exported file paths."""
    model_id = f"model_{uuid.uuid4().hex[:12]}"
    script_content = EXECUTOR_TEMPLATE.format(code=textwrap.indent(code, "    "))

    script_path = OUTPUT_DIR / f"{model_id}.py"
    script_path.write_text(script_content, encoding="utf-8")

    try:
        result = subprocess.run(
            [CAD_PYTHON, str(script_path), str(OUTPUT_DIR), model_id, export_fmt],
            capture_output=True,
            text=True,
            timeout=60,
            env={**os.environ, "PYTHONPATH": ""},
        )

        if result.returncode != 0:
            return {
                "status": "error",
                "error": result.stderr or result.stdout or "Unknown error",
                "script": str(script_path),
            }

        try:
            return json.loads(result.stdout.strip().split("\n")[-1])
        except json.JSONDecodeError:
            return {"status": "error", "error": f"Invalid output: {result.stdout}", "stderr": result.stderr}

    except subprocess.TimeoutExpired:
        return {"status": "error", "error": "Execution timed out (60s limit)"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def get_templates() -> Dict[str, Dict[str, str]]:
    """Return available parametric templates."""
    return {
        "enclosure": {
            "name": "Электронный корпус",
            "description": "Корпус для электроники с крепёжными отверстиями",
            "code": textwrap.dedent("""\
                from build123d import *
                import math

                width = 80.0
                depth = 50.0
                height = 25.0
                wall = 2.0
                screw_r = 1.7

                outer = Box(width, depth, height)
                inner = Box(width - wall*2, depth - wall*2, height - wall)
                shape = outer - inner

                for x, y in [(-1,-1),(-1,1),(1,-1),(1,1)]:
                    cx = x * (width/2 - 5)
                    cy = y * (depth/2 - 5)
                    hole = Location((cx, cy, 0)) * Cylinder(screw_r, height + 2)
                    shape = shape - hole
            """),
        },
        "bracket": {
            "name": "Кронштейн L",
            "description": "L-образный кронштейн с отверстиями",
            "code": textwrap.dedent("""\
                from build123d import *

                width = 40.0
                depth = 30.0
                height = 40.0
                thickness = 4.0
                hole_d = 5.0

                base = Box(width, depth, thickness)
                vert = Box(width, thickness, height, align=(Align.CENTER, Align.MIN, Align.MIN))
                vert = vert.move(Location((0, 0, thickness)))

                shape = base + vert

                for cx in [-width/2+8, width/2-8]:
                    h = Location((cx, 0, height-8)) * Cylinder(hole_d/2, thickness + 4)
                    shape = shape - h
            """),
        },
        "gear": {
            "name": "Зубчатое колесо",
            "description": "Простая шестерёнка с зубьями (упрощённая)",
            "code": textwrap.dedent("""\
                from build123d import *
                import math

                teeth = 16
                r_outer = 20.0
                r_root = 16.0
                thickness = 8.0
                bore_d = 6.0
                tooth_angle = 2 * math.pi / teeth

                body = Cylinder(r_outer, thickness)

                for i in range(teeth):
                    a = i * tooth_angle
                    notch = Location((r_root * 0.9 * math.cos(a), r_root * 0.9 * math.sin(a), 0)) * Box(
                        r_root * 0.3, r_root * 0.25, thickness + 2,
                        rotation=(0, 0, math.degrees(a))
                    )
                    body = body - notch

                bore = Cylinder(bore_d/2, thickness + 2)
                shape = body - bore
            """),
        },
        "phone_stand": {
            "name": "Держатель телефона",
            "description": "Угловой держатель с вырезом для кабеля",
            "code": textwrap.dedent("""\
                from build123d import *
                import math

                width = 80.0
                base_depth = 60.0
                base_h = 4.0
                back_h = 80.0
                back_t = 4.0
                lip_h = 12.0
                cable_r = 5.0

                base = Box(width, base_depth, base_h, align=(Align.CENTER, Align.CENTER, Align.MIN))
                back = Box(width, back_t, back_h, align=(Align.CENTER, Align.MIN, Align.MIN))
                back = back.move(Location((0, base_depth/2 - back_t/2, base_h)))

                lip = Box(width, 8, lip_h, align=(Align.CENTER, Align.MIN, Align.MIN))
                lip = lip.move(Location((0, -base_depth/2 + 4, base_h)))

                shape = base + back + lip

                cable = Location((0, -base_depth/2, base_h/2)) * Cylinder(cable_r, base_h + 4)
                shape = shape - cable
            """),
        },
        "gridfinity_bin": {
            "name": "Gridfinity лоток",
            "description": "Стандартный лоток 42мм Gridfinity",
            "code": textwrap.dedent("""\
                from build123d import *

                grid_x = 2
                grid_y = 1
                unit_height = 3
                wall = 2.0
                unit_size = 42.0
                height = unit_height * 7.0 + 4.4

                w = grid_x * unit_size
                d = grid_y * unit_size

                outer = Box(w, d, height)
                inner = Box(w - wall*2, d - wall*2, height - 3.0)
                inner = inner.move(Location((0, 0, 1.5)))

                shape = outer - inner
            """),
        },
        "pipe_adapter": {
            "name": "Переходник труб",
            "description": "Конусный переходник между трубами разных диаметров",
            "code": textwrap.dedent("""\
                from build123d import *

                d1 = 40.0
                d2 = 25.0
                length = 60.0
                wall = 2.5

                outer = Cone(d1/2, d2/2, length, align=(Align.CENTER, Align.CENTER, Align.MIN))
                inner = Cone(d1/2 - wall, d2/2 - wall, length, align=(Align.CENTER, Align.CENTER, Align.MIN))

                shape = outer - inner
            """),
        },
        "bearing_mount": {
            "name": "Крепление подшипника",
            "description": "Кронштейн для подшипника с крепёжными отверстиями",
            "code": textwrap.dedent("""\
                from build123d import *

                bearing_od = 22.0
                bearing_w = 7.0
                mount_h = 35.0
                mount_w = 50.0
                thickness = 5.0
                hole_d = 4.5

                block = Box(mount_w, bearing_od + thickness*2, mount_h)
                bore = Location((0, 0, mount_h/2)) * Cylinder(bearing_od/2, bearing_w + 2)
                shape = block - bore

                for cx in [-mount_w/2+8, mount_w/2-8]:
                    h = Location((cx, 0, 0)) * Cylinder(hole_d/2, mount_h + 2)
                    shape = shape - h
            """),
        },
        "led_panel": {
            "name": "Панель для LED",
            "description": "Панель с рядами отверстий под LED",
            "code": textwrap.dedent("""\
                from build123d import *

                rows = 4
                cols = 8
                led_d = 5.0
                spacing = 12.0
                margin = 5.0
                thickness = 2.0

                pw = cols * spacing + margin * 2
                ph = rows * spacing + margin * 2
                panel = Box(pw, ph, thickness)

                for x in range(cols):
                    for y in range(rows):
                        cx = x * spacing + margin + spacing/2 - pw/2
                        cy = y * spacing + margin + spacing/2 - ph/2
                        hole = Location((cx, cy, 0)) * Cylinder(led_d/2, thickness + 2)
                        panel = panel - hole

                shape = panel
            """),
        },
        "simple_house": {
            "name": "Домик (модель)",
            "description": "Простая модель домика — стены + крыша",
            "code": textwrap.dedent("""\
                from build123d import *
                import math

                w = 60.0
                d = 40.0
                wall_h = 30.0
                wall_t = 2.0
                roof_h = 20.0

                walls_outer = Box(w, d, wall_h)
                walls_inner = Box(w - wall_t*2, d - wall_t*2, wall_h - wall_t)
                walls = walls_outer - walls_inner

                roof_angle = math.atan2(roof_h, d/2)
                roof = Box(w + 4, d/2 + 2, roof_h, align=(Align.CENTER, Align.MIN, Align.MIN))
                roof = roof.move(Location((0, 0, wall_h)))

                shape = walls + roof
            """),
        },
        "cable_clip": {
            "name": "Клипса для кабеля",
            "description": "Настенная клипса для удержания кабеля",
            "code": textwrap.dedent("""\
                from build123d import *

                cable_d = 6.0
                clip_w = 15.0
                clip_h = 20.0
                wall = 2.5
                gap = 1.5

                base = Box(clip_w, wall, clip_h, align=(Align.CENTER, Align.MIN, Align.MIN))
                side_l = Box(wall, clip_w/2, clip_h, align=(Align.MIN, Align.MIN, Align.MIN))
                side_l = side_l.move(Location((-clip_w/2 + wall, 0, 0)))
                side_r = Box(wall, clip_w/2, clip_h, align=(Align.MAX, Align.MIN, Align.MIN))
                side_r = side_r.move(Location((clip_w/2 - wall, 0, 0)))

                shape = base + side_l + side_r

                bore = Location((0, cable_d/2 + wall, clip_h/2)) * Cylinder(cable_d/2, clip_w + 2)
                shape = shape - bore
            """),
        },
    }


SYSTEM_PROMPT = textwrap.dedent("""\
You are a build123d CAD code generator. Generate ONLY valid Python code using the build123d library.

CRITICAL API reference (build123d v0.10.0):
- Box(length, width, height) — 3 separate float arguments, NOT tuple
- Cylinder(radius, height) — radius is a float
- Sphere(radius) — radius is a float
- Cone(radius_top, radius_bottom, height)
- Location((x, y, z)) * shape — positions a shape (note: Location takes a tuple)
- shape.move(Location((x, y, z))) — moves existing shape
- shape + other — union
- shape - other — subtraction
- fillet(shape.edges(), radius) — rounds edges
- chamfer(shape.edges(), distance) — adds chamfer
- extrude(sketch, amount) — extrudes a sketch

Rules:
- Start with: from build123d import *
- Put the final result in a variable called `shape`
- Use named variables for ALL dimensions at the top (parametric)
- Units are millimeters
- Do NOT use translate() — use .move(Location(...)) or Location * shape
- Do NOT use Polyline in BuildSketch — use Line instead
- Output ONLY the Python code, nothing else (no markdown, no explanation)
- Code must be complete and runnable

Example of correct code:
    from build123d import *
    width = 80.0
    depth = 50.0
    height = 25.0
    shape = Box(width, depth, height)
""").strip()


def generate_code_from_nl(description: str, max_retries: int = 2) -> Dict[str, Any]:
    """Generate build123d code from a natural language description using ollama."""
    if httpx is None:
        return {"error": "httpx not installed. Run: pip install httpx"}

    prompt = f"Generate build123d Python code for this 3D model:\n\n{description}\n\nOutput ONLY the Python code. No markdown, no explanation."

    # Disable proxy for localhost
    env_proxies = {}
    for k in list(os.environ.keys()):
        if 'proxy' in k.lower():
            env_proxies[k] = os.environ.pop(k)

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            with httpx.Client(timeout=120.0, proxy=None) as client:
                resp = client.post(
                    f"{OLLAMA_URL}/api/chat",
                    json={
                        "model": OLLAMA_MODEL,
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": prompt},
                        ],
                        "stream": False,
                        "options": {
                            "temperature": 0.1,
                            "num_predict": 2048,
                        },
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            raw = data.get("message", {}).get("content", "")
            code = extract_code_block(raw)

            if not code:
                last_error = "AI did not return valid code"
                continue

            # Validate code can be parsed
            compile(code, "<ai_gen>", "exec")
            return {"code": code, "model": OLLAMA_MODEL}

        except SyntaxError as e:
            last_error = f"Generated code has syntax error: {e}"
            continue
        except httpx.ConnectError:
            return {"error": f"Cannot connect to ollama at {OLLAMA_URL}. Is it running?"}
        except Exception as e:
            last_error = str(e)
            continue
        finally:
            # Restore proxy env vars
            os.environ.update(env_proxies)

    return {"error": f"Failed after {max_retries+1} attempts. Last error: {last_error}"}


def extract_code_block(text: str) -> str:
    """Extract Python code from AI response (handles markdown fences)."""
    # Try ```python ... ``` blocks
    blocks = re.findall(r'```(?:python)?\s*\n(.*?)```', text, re.DOTALL)
    if blocks:
        return blocks[0].strip()

    # Try to find code starting with import
    lines = text.split('\n')
    code_lines = []
    in_code = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(('from build123d', 'import build123d', 'import ', 'from ')):
            in_code = True
        if in_code:
            if stripped and not stripped.startswith(('#', '"""', "'''")):
                code_lines.append(line)
            elif code_lines and stripped.startswith(('"""', "'''")):
                break

    if code_lines:
        return '\n'.join(code_lines).strip()

    return text.strip()


def try_fix_common_errors(code: str) -> str:
    """Try to fix common build123d code generation errors."""
    fixed = code

    # Fix: base.chamfer(edges(), d) -> chamfer(base.edges(), d)
    fixed = re.sub(
        r'(\w+)\.chamfer\(edges\(\)',
        r'chamfer(\1.edges()',
        fixed
    )

    # Fix: base.fillet(edges(), r) -> fillet(base.edges(), r)
    fixed = re.sub(
        r'(\w+)\.fillet\(edges\(\)',
        r'fillet(\1.edges()',
        fixed
    )

    # Fix: translate(obj, (x,y,z)) -> obj.move(Location((x,y,z)))
    fixed = re.sub(
        r'translate\((\w+),\s*\(([^)]+)\)\)',
        r'\1.move(Location((\2)))',
        fixed
    )

    # Fix: Box(Location(...), (w,d,h)) -> Box(w,d,h)
    fixed = re.sub(
        r'Box\(Location\([^)]*\),\s*\((\d+\.?\d*),\s*(\d+\.?\d*),\s*(\d+\.?\d*)\)\)',
        r'Box(\1, \2, \3)',
        fixed
    )

    return fixed
