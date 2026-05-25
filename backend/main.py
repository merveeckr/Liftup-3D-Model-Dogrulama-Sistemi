import os
import sys
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import BaseModel, Field
import uvicorn

sys.path.insert(0, os.path.dirname(__file__))
from pipeline import run_pipeline
from database import init_db, save_analysis, list_analyses, get_analysis, delete_analysis, clear_all
from report import generate_pdf
from export import generate_excel, generate_history_excel

app = FastAPI(
    title="LIFT UP — Yapay Zeka Destekli 3D Model Doğrulama",
    version="1.1.0",
)

init_db()

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
    analysis_id = save_analysis(req.model, req.n_points, req.noise_std, req.defect_count, result)
    result["analysis_id"] = analysis_id
    return result


@app.get("/api/history")
def get_history(limit: int = 100):
    """Kayıtlı analiz geçmişini listele."""
    return {"history": list_analyses(limit)}


@app.get("/api/history/{analysis_id}")
def get_history_item(analysis_id: int):
    """Belirli bir analiz kaydını tam veriyle getir."""
    item = get_analysis(analysis_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Analiz kaydı bulunamadı")
    return item


@app.delete("/api/history/{analysis_id}")
def delete_history_item(analysis_id: int):
    """Bir analiz kaydını sil."""
    if not delete_analysis(analysis_id):
        raise HTTPException(status_code=404, detail="Analiz kaydı bulunamadı")
    return {"success": True}


@app.delete("/api/history")
def clear_history():
    """Tüm geçmişi temizle."""
    count = clear_all()
    return {"deleted": count}


PDF_DIR = os.path.join(os.path.expanduser("~"), "Desktop", "LIFTUP PDF")
os.makedirs(PDF_DIR, exist_ok=True)


@app.get("/api/stats")
def get_stats():
    """Tüm geçmiş analizlerin istatistik özetini döndür."""
    history = list_analyses(500)
    if not history:
        return {"count": 0}

    conformances = [h["conformance"] for h in history]
    rms_values   = [h["rms"] for h in history]

    verdicts = {}
    risks    = {}
    models   = {}
    for h in history:
        verdicts[h["verdict"]]      = verdicts.get(h["verdict"], 0) + 1
        risks[h["overall_risk"]]    = risks.get(h["overall_risk"], 0) + 1
        models[h["model"]]          = models.get(h["model"], 0) + 1

    best  = max(history, key=lambda h: h["conformance"])
    worst = min(history, key=lambda h: h["conformance"])

    trend = [
        {"id": h["id"], "conformance": h["conformance"],
         "verdict": h["verdict"], "date": h["timestamp"][:10]}
        for h in reversed(history[:20])
    ]

    return {
        "count":           len(history),
        "avg_conformance": round(sum(conformances) / len(conformances), 2),
        "avg_rms":         round(sum(rms_values)   / len(rms_values),   4),
        "max_conformance": round(max(conformances), 2),
        "min_conformance": round(min(conformances), 2),
        "best":  {"id": best["id"],  "model": best["model"],
                  "conformance": best["conformance"],  "timestamp": best["timestamp"]},
        "worst": {"id": worst["id"], "model": worst["model"],
                  "conformance": worst["conformance"], "timestamp": worst["timestamp"]},
        "verdicts": verdicts,
        "risks":    risks,
        "models":   models,
        "trend":    trend,
    }


@app.get("/api/compare")
def compare_analyses(id1: int, id2: int):
    """İki analizi karşılaştır, delta metrikler ve kazananları döndür."""
    a = get_analysis(id1)
    b = get_analysis(id2)
    if a is None or b is None:
        raise HTTPException(status_code=404, detail="Analiz kaydı bulunamadı")

    sa = a["result"]["stats"]
    sb = b["result"]["stats"]

    metric_keys = ["conformance", "rms", "max_deviation", "mean_deviation",
                   "anomaly_count", "icp_rmse"]
    # Düşük mü yoksa yüksek mi iyi?
    higher_is_better = {"conformance"}

    deltas, winners = {}, {}
    for k in metric_keys:
        if k not in sa or k not in sb:
            continue
        d = round(sb[k] - sa[k], 4)
        deltas[k] = d
        if d == 0:
            winners[k] = "tie"
        elif k in higher_is_better:
            winners[k] = "b" if d > 0 else "a"
        else:
            winners[k] = "b" if d < 0 else "a"

    # Genel kazanan: kazanılan metrik sayısına göre
    wa = sum(1 for w in winners.values() if w == "a")
    wb = sum(1 for w in winners.values() if w == "b")
    overall = "a" if wa > wb else ("b" if wb > wa else "tie")

    return {
        "a": {"id": id1, "model": a["model"], "timestamp": a["timestamp"],
              "stats": sa},
        "b": {"id": id2, "model": b["model"], "timestamp": b["timestamp"],
              "stats": sb},
        "deltas":  deltas,
        "winners": winners,
        "overall": overall,
        "score":   {"a": wa, "b": wb},
    }


@app.get("/api/report/{analysis_id}")
def save_report(analysis_id: int):
    """PDF raporu masaüstündeki 'liftup pdf ler' klasörüne kaydeder."""
    item = get_analysis(analysis_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Analiz kaydı bulunamadı")
    pdf_bytes = generate_pdf(item)
    filename  = f"liftup_analiz_{analysis_id}.pdf"
    path      = os.path.join(PDF_DIR, filename)
    with open(path, "wb") as f:
        f.write(pdf_bytes)
    return {"success": True, "path": path, "filename": filename}


@app.get("/api/excel/{analysis_id}")
def save_excel(analysis_id: int):
    """Analiz sonuçlarını Excel olarak LIFTUP PDF klasörüne kaydeder."""
    item = get_analysis(analysis_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Analiz kaydı bulunamadı")
    xlsx_bytes = generate_excel(item)
    filename   = f"liftup_analiz_{analysis_id}.xlsx"
    path       = os.path.join(PDF_DIR, filename)
    with open(path, "wb") as f:
        f.write(xlsx_bytes)
    return {"success": True, "path": path, "filename": filename}


@app.get("/api/excel-history")
def save_history_excel():
    """Tüm analiz geçmişini Excel olarak LIFTUP PDF klasörüne kaydeder."""
    history = list_analyses(500)
    if not history:
        raise HTTPException(status_code=404, detail="Geçmiş boş")
    xlsx_bytes = generate_history_excel(history)
    filename   = f"liftup_gecmis_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    path       = os.path.join(PDF_DIR, filename)
    with open(path, "wb") as f:
        f.write(xlsx_bytes)
    return {"success": True, "path": path, "filename": filename}


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "1.1.0"}


if __name__ == "__main__":
    print("=" * 55)
    print("  LIFT UP — 3D Model Doğrulama Sistemi")
    print("  http://localhost:8000")
    print("=" * 55)
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
