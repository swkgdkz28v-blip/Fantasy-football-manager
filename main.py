from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import os

from routers.analysis import router as analysis_router

app = FastAPI(title="Fantasy Football Manager", version="10.33")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analysis_router)

@app.get("/health")
async def health():
    return {"status": "ok", "version": "10.33"}

FRONTEND = Path(__file__).parent / "frontend"

# CSS, JS, icons and manifest live in frontend/ and are served under /static/...
app.mount("/static", StaticFiles(directory=FRONTEND), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    # no-cache so a new deploy is picked up right away; the files it loads carry a ?v= version tag
    return HTMLResponse(content=(FRONTEND / "index.html").read_text(),
                        headers={"Cache-Control": "no-cache"})
