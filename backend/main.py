import os
import json
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, BackgroundTasks, File, UploadFile, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from core.translator import translate_single_file, parse_srt, detect_encoding
from core.batch import start_batch_job, stop_batch_job, get_batch_status, get_log_generator
from core.config import get_settings, update_settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Retrieve settings to initialize scheduler if it's supposed to be active
    from core.scheduler import get_scheduler, configure_scheduler
    
    configure_scheduler()
    scheduler = get_scheduler()
    scheduler.start()
    
    yield
    
    scheduler.shutdown()

app = FastAPI(title="Sub-Trans Manager", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- API Endpoints ---
@app.get("/api/config")
def read_config():
    return get_settings()

@app.post("/api/config")
def write_config(settings: dict):
    return update_settings(settings)

@app.get("/api/media")
def list_media():
    settings = get_settings()
    films_path = settings.get("films_path", "/Films")
    series_path = settings.get("series_path", "/Series")
    
    media = []
    
    for path, kind in [(films_path, "film"), (series_path, "series")]:
        if os.path.exists(path):
            for root, dirs, files in os.walk(path):
                # Check directly in the root where .srt files exist
                for file in files:
                    file_lower = file.lower()
                    if file_lower.endswith(".srt"):
                        # If we found an SRT, identify its base
                        is_eng = any(x in file_lower for x in [".en.", ".eng.", ".hi.", ".en.hi.", ".eng.hi."])
                        is_nl = any(x in file_lower for x in [".nl.", ".dut."])
                        # Register directory mapping
                        existing = next((m for m in media if m["path"] == root), None)
                        if not existing:
                            existing = {
                                "path": root,
                                "name": os.path.basename(root),
                                "kind": kind,
                                "has_en": False,
                                "has_nl": False,
                                "en_file": None,
                                "nl_file": None
                            }
                            media.append(existing)
                        
                        if is_eng:
                            existing["has_en"] = True
                            existing["en_file"] = os.path.join(root, file)
                        if is_nl:
                            existing["has_nl"] = True
                            existing["nl_file"] = os.path.join(root, file)
    return {"media": media}

@app.post("/api/translate")
async def api_translate_single(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    file_path = data.get("file_path")
    if not file_path or not os.path.exists(file_path):
        return JSONResponse(status_code=400, content={"error": "File not found"})
    
    background_tasks.add_task(translate_single_file, file_path)
    return {"status": "started", "file": file_path}

@app.get("/api/srt")
def read_srt(file_path: str):
    if not os.path.exists(file_path):
        return JSONResponse(status_code=404, content={"error": "File not found"})
    
    with open(file_path, "rb") as f:
        bytes_data = f.read()
    encoding = detect_encoding(bytes_data) or 'utf-8'
    content = bytes_data.decode(encoding, errors='ignore')
    return {"parsed": parse_srt(content)}

@app.post("/api/srt")
async def save_srt(request: Request):
    data = await request.json()
    file_path = data.get("file_path")
    parsed = data.get("parsed")
    
    if not file_path or not parsed:
        return JSONResponse(status_code=400, content={"error": "Invalid request"})
        
    final_srt = "\n".join([f"{o['index']}\n{o['time']}\n{o['text']}\n" for o in parsed])
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(final_srt)
    return {"status": "saved"}

@app.get("/api/batch")
def get_batch():
    return get_batch_status()

@app.post("/api/batch/start")
async def api_start_batch(background_tasks: BackgroundTasks):
    background_tasks.add_task(start_batch_job)
    return {"status": "started"}

@app.post("/api/batch/stop")
def api_stop_batch():
    stop_batch_job()
    return {"status": "stopped"}

@app.get("/api/logs")
async def stream_logs(request: Request):
    return EventSourceResponse(get_log_generator(request))

@app.post("/api/refresh")
async def trigger_refresh(request: Request):
    # Dummy webhook for jellyfin
    # Typically POST to http://jellyfin:8096/Library/Refresh?api_key=...
    data = await request.json()
    # Implement standard HTTPX post with settings
    return {"status": "webhook triggered"}

# --- Serve Frontend SPA ---
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
else:
    @app.get("/")
    def index():
        return {"error": "Frontend not built yet. Run npm run build in /frontend and restart."}
