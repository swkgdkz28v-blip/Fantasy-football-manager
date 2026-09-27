from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import os

from routers.analysis import router as analysis_router

app = FastAPI(title="Fantasy Football Manager", version="10.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analysis_router)

@app.get("/health")
async def health():
    return {"status": "ok", "version": "10.1"}

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    html_path = Path(__file__).parent / "frontend" / "index.html"
    return HTMLResponse(content=html_path.read_text())
