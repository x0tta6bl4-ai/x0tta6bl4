#!/usr/bin/env python3
"""Микросервис локальных ML моделей для Basis-Web"""
import json
import logging
from pathlib import Path
from typing import Dict, Any
import numpy as np

try:
    import joblib
except ImportError:
    joblib = None

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODELS_DIR = Path("/mnt/AC74CC2974CBF3DC/x0tta6bl4_paradox_zone/x0tta6bl4/models")

class PredictionRequest(BaseModel):
    model_name: str = "demo_classifier"
    input_data: Dict[str, Any]

class LocalModelService:
    def __init__(self, models_dir: Path = MODELS_DIR):
        self.models_dir = models_dir
        self.loaded_models = {}
        logger.info(f"✅ LocalModelService инициализирован")
    
    def list_available_models(self) -> Dict[str, Any]:
        models = []
        if self.models_dir.exists():
            for f in self.models_dir.glob("*.joblib"):
                models.append({"name": f.stem, "type": "joblib", "size": f.stat().st_size})
        return {"total": len(models), "models": models}
    
    def load_model(self, model_name: str) -> bool:
        if model_name in self.loaded_models or not joblib:
            return True
        try:
            path = self.models_dir / f"{model_name}.joblib"
            if path.exists():
                self.loaded_models[model_name] = joblib.load(path)
                return True
        except Exception as e:
            logger.error(f"❌ Error: {e}")
        return False
    
    def predict_cabinet_type(self, width: int, height: int, depth: int) -> Dict:
        if not self.load_model("demo_classifier"):
            return {"error": "Model not available", "success": False}
        try:
            model = self.loaded_models.get("demo_classifier")
            features = np.array([[width, height, depth]], dtype=np.float32)
            prediction = model.predict(features)[0]
            return {"success": True, "cabinet_type": str(prediction), "input": {"width": width, "height": height, "depth": depth}}
        except Exception as e:
            return {"error": str(e), "success": False}
    
    def predict_complexity(self, width: int, height: int, depth: int) -> Dict:
        if not self.load_model("demo_regressor"):
            return {"error": "Model not available", "success": False}
        try:
            model = self.loaded_models.get("demo_regressor")
            features = np.array([[width, height, depth, 2, 3]], dtype=np.float32)
            prediction = model.predict(features)[0]
            return {"success": True, "complexity_score": float(prediction), "complexity_level": "low" if prediction < 0.33 else "high"}
        except Exception as e:
            return {"error": str(e), "success": False}

app = FastAPI(title="Basis-Web Local AI", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
service = LocalModelService()

@app.get("/health")
async def health():
    return {"status": "healthy", "has_joblib": joblib is not None}

@app.get("/models")
async def list_models():
    return service.list_available_models()

@app.post("/predict/cabinet-type")
async def predict_cabinet_type(req: PredictionRequest):
    return service.predict_cabinet_type(req.input_data.get("width", 1000), req.input_data.get("height", 2000), req.input_data.get("depth", 500))

@app.post("/predict/complexity")
async def predict_complexity(req: PredictionRequest):
    return service.predict_complexity(req.input_data.get("width", 1000), req.input_data.get("height", 2000), req.input_data.get("depth", 500))

@app.get("/version")
async def version():
    return {"version": "1.0.0"}

if __name__ == "__main__":
    logger.info("🚀 Starting on http://127.0.0.1:8001")
    uvicorn.run(app, host="127.0.0.1", port=8001)
