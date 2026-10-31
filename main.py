from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import os
import re

from routers.analysis import router as analysis_router

# Version is set once, in frontend/index.html (<meta name="app-version">)
_m = re.search(r'name="app-version" content="([^"]+)"', (Path(__file__).parent / "frontend" / "index.html").read_text())
APP_VERSION = _m.group(1) if _m else "dev"

app = FastAPI(title="Fantasy Football Manager", version=APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analysis_router)

@app.get("/health")
async def health():
    return {"status": "ok", "version": APP_VERSION}

FRONTEND = Path(__file__).parent / "frontend"

# CSS, JS, icons and manifest live in frontend/ and are served under /static/...
app.mount("/static", StaticFiles(directory=FRONTEND), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    # no-cache so a new deploy is picked up right away; the files it loads carry a ?v= version tag
    return HTMLResponse(content=(FRONTEND / "index.html").read_text(),
                        headers={"Cache-Control": "no-cache"})
