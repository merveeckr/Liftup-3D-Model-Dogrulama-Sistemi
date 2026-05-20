import os
import sys

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field
import uvicorn

# pipeline.py'nin aynı dizinde olduğundan emin ol
sys.path.insert(0, os.path.dirname(__file__))
from pipeline import run_pipeline

app = FastAPI(
    title="LIFT UP — Yapay Zeka Destekli 3D Model Doğrulama",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")


class AnalysisRequest(BaseModel):
    model: str = Field(default="sedefe1.stl", description="STL dosyası adı")
    n_points: int = Field(default=8000, ge=1000, le=30000)
    noise_std: float = Field(default=0.3, ge=0.0, le=5.0)
    defect_count: int = Field(default=3, ge=0, le=10)
    seed: int = Field(default=None, description="Tekrarlanabilirlik için seed")


@app.get("/", include_in_schema=False)
def serve_index():
    path = os.path.join(FRONTEND_DIR, "index.html")
    if not os.path.exists(path):
        return HTMLResponse("<h2>frontend/index.html bulunamadı</h2>", status_code=404)
    return FileResponse(path)


@app.get("/api/models")
def list_models():
    """Mevcut STL dosyalarını listele."""
    stl_files = [f for f in os.listdir(BASE_DIR) if f.lower().endswith(".stl")]
    return {"models": sorted(stl_files)}


@app.get("/models/{filename}", include_in_schema=False)
def serve_model(filename: str):
    """STL dosyasını Three.js STLLoader için sun."""
    if not filename.lower().endswith(".stl"):
        raise HTTPException(status_code=400, detail="Sadece .stl dosyaları")
    path = os.path.join(BASE_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"{filename} bulunamadı")
    return FileResponse(path, media_type="application/octet-stream")


@app.post("/api/analyze")
def analyze(req: AnalysisRequest):
    """
    Tam doğrulama pipeline'ını çalıştırır:
    STL yükle → tarama simüle et → ICP hizala → sapma hesapla → anomali tespit
    """
    stl_path = os.path.join(BASE_DIR, req.model)
    if not os.path.exists(stl_path):
        raise HTTPException(status_code=404, detail=f"Model bulunamadı: {req.model}")

    result = run_pipeline(
        stl_path=stl_path,
        n_points=req.n_points,
        noise_std=req.noise_std,
        defect_count=req.defect_count,
        seed=req.seed,
    )
    return result


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


if __name__ == "__main__":
    print("=" * 55)
    print("  LIFT UP — 3D Model Doğrulama Sistemi")
    print("  http://localhost:8000")
    print("=" * 55)
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
