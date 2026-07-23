from __future__ import annotations

import os
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional

import generators
import ai_gen

app = FastAPI(title="AI 3D CAD Studio", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUT_DIR = Path("/mnt/projects/3d-generator-app/output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class CodeRequest(BaseModel):
    code: str
    export_fmt: str = "both"


class NLRequest(BaseModel):
    description: str
    export_fmt: str = "both"


class AdapterRequest(BaseModel):
    d1_outer: float = 35.0
    d2_outer: float = 32.0
    length: float = 75.0
    wall_thickness: float = 2.5


class PlywoodBoxRequest(BaseModel):
    length: float = 200.0
    width: float = 140.0
    height: float = 90.0
    plywood_thickness: float = 6.0
    tool_diameter: float = 3.175


class GridfinityRequest(BaseModel):
    grid_x: int = 2
    grid_y: int = 1
    unit_height: int = 3
    wall_thickness: float = 2.0


@app.post("/api/generate/code")
async def generate_from_code(req: CodeRequest):
    result = ai_gen.run_build123d_code(req.code, req.export_fmt)
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
    files = {}
    for fmt, path in result.get("files", {}).items():
        files[fmt] = f"/download/{Path(path).name}"
    return {"status": "success", "files": files}


@app.post("/api/generate/nl")
async def generate_from_nl(req: NLRequest):
    gen = ai_gen.generate_code_from_nl(req.description)
    if "error" in gen:
        raise HTTPException(status_code=500, detail=gen["error"])

    code = gen["code"]
    result = ai_gen.run_build123d_code(code, req.export_fmt)

    # If execution failed, try fixing common errors
    if result.get("status") == "error":
        fixed_code = ai_gen.try_fix_common_errors(code)
        if fixed_code != code:
            result = ai_gen.run_build123d_code(fixed_code, req.export_fmt)
            if result.get("status") == "success":
                code = fixed_code

    if result.get("status") == "error":
        return {
            "status": "partial",
            "code": code,
            "error": result.get("error", "Execution failed"),
        }

    files = {}
    for fmt, path in result.get("files", {}).items():
        files[fmt] = f"/download/{Path(path).name}"
    return {"status": "success", "code": code, "files": files}


@app.get("/api/default-model")
async def get_default_model():
    for name, stl_name, glb_name in [
        ("Grogu (FLUX + TripoSR AI v2)", "grogu_v2.stl", "grogu_v2.glb"),
        ("Grogu (FLUX + TripoSR AI)", "grogu_final.stl", "grogu_final_clean.glb"),
        ("Grogu (TripoSR AI v2)", "grogu_highres.stl", "grogu_highres.glb"),
        ("Grogu (Hunyuan3D AI)", "grogu_hunyuan3d.stl", "grogu_hunyuan3d.glb"),
        ("Grogu v3 (детализированный)", "grogu_v3.stl", "grogu_v3.step"),
        ("Grogu", "grogu.stl", "grogu.step"),
    ]:
        stl_path = OUTPUT_DIR / stl_name
        if stl_path.exists():
            glb_path = OUTPUT_DIR / glb_name
            return {
                "status": "success",
                "name": name,
                "stl": f"/download/{stl_path.name}",
                "step": f"/download/{glb_path.name}" if glb_path.exists() else None,
            }
    return {"status": "none"}


@app.get("/api/templates")
async def get_templates():
    templates = ai_gen.get_templates()
    return {
        k: {"name": v["name"], "description": v["description"]}
        for k, v in templates.items()
    }


@app.get("/api/templates/{template_id}/code")
async def get_template_code(template_id: str):
    templates = ai_gen.get_templates()
    if template_id not in templates:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"code": templates[template_id]["code"]}


@app.post("/api/generate/adapter")
async def generate_adapter_endpoint(req: AdapterRequest):
    try:
        res = generators.generate_adapter(
            d1_outer=req.d1_outer,
            d2_outer=req.d2_outer,
            length=req.length,
            wall_thickness=req.wall_thickness,
            output_dir=OUTPUT_DIR,
        )
        return {
            "status": "success",
            "files": {
                "stl": f"/download/{Path(res['stl']).name}",
                "step": f"/download/{Path(res['step']).name}",
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate/plywood_box")
async def generate_plywood_box_endpoint(req: PlywoodBoxRequest):
    try:
        res = generators.generate_plywood_box(
            length=req.length,
            width=req.width,
            height=req.height,
            plywood_thickness=req.plywood_thickness,
            tool_diameter=req.tool_diameter,
            output_dir=OUTPUT_DIR,
        )
        return {
            "status": "success",
            "files": {
                "stl": f"/download/{Path(res['stl']).name}",
                "step": f"/download/{Path(res['step']).name}",
                "dxf": f"/download/{Path(res['dxf']).name}",
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate/gridfinity")
async def generate_gridfinity_endpoint(req: GridfinityRequest):
    try:
        res = generators.generate_gridfinity(
            grid_x=req.grid_x,
            grid_y=req.grid_y,
            unit_height=req.unit_height,
            wall_thickness=req.wall_thickness,
            output_dir=OUTPUT_DIR,
        )
        return {
            "status": "success",
            "files": {
                "stl": f"/download/{Path(res['stl']).name}",
                "step": f"/download/{Path(res['step']).name}",
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/download/{filename}")
async def download_file(filename: str):
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=file_path, filename=filename)


STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8095, reload=True)
