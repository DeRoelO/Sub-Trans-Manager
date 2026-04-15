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
    import re
    settings = get_settings()
    films_path = settings.get("films_path", "/Films")
    series_path = settings.get("series_path", "/Series")
    
    media = []
    
    for path, kind in [(films_path, "film"), (series_path, "series")]:
        if os.path.exists(path):
            for root, dirs, files in os.walk(path):
                # Search for any subtitle files representing an episode/movie
                for file in files:
                    file_lower = file.lower()
                    if file_lower.endswith(".srt"):
                        # Define the core "show_name_episode" base
                        base_name_match = re.sub(r'\.(en|eng|hi|nl|dut|en\.hi|eng\.hi)\.srt$', '', file, flags=re.IGNORECASE)
                        if base_name_match == file:
                            base_name_match = file.replace(".srt", "")
                            
                        full_base_path = os.path.join(root, base_name_match)
                        
                        # Find if we already registered this episode/video
                        existing = next((m for m in media if m["base_path"] == full_base_path), None)
                        if not existing:
                            # Parse out directory path context for neat display
                            rel_path = os.path.relpath(root, start=path)
                            display_dir = rel_path if rel_path != "." else os.path.basename(root)

                            existing = {
                                "base_path": full_base_path,
                                "name": base_name_match, 
                                "group": display_dir, 
                                "kind": kind,
                                "has_en": False,
                                "has_nl": False,
                                "has_bak": False,
                                "en_file": None,
                                "nl_file": None,
                                "bak_file": None
                            }
                            media.append(existing)
                        
                        is_eng = any(x in file_lower for x in [".en.", ".eng.", ".hi.", ".en.hi.", ".eng.hi."])
                        is_nl = any(x in file_lower for x in [".nl.", ".dut."])
                        
                        if is_eng:
                            existing["has_en"] = True
                            existing["en_file"] = os.path.join(root, file)
                            bak_path = os.path.join(root, file) + ".bak"
                            if os.path.exists(bak_path):
                                existing["has_bak"] = True
                                existing["bak_file"] = bak_path
                        if is_nl:
                            existing["has_nl"] = True
                            existing["nl_file"] = os.path.join(root, file)
    return {"media": media}

@app.post("/api/translate")
async def api_translate_single(request: Request, background_tasks: BackgroundTasks):
    from core.batch import append_log
    data = await request.json()
    file_path = data.get("file_path")
    if not file_path or not os.path.exists(file_path):
        return JSONResponse(status_code=400, content={"error": "File not found"})
    
    append_log(f"🟢 [HANDMATIG] Translate request triggered for {os.path.basename(file_path)}")
    background_tasks.add_task(translate_single_file, file_path, log_callback=append_log)
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
    import httpx
    settings = get_settings()
    webhook = settings.get("jellyfin_webhook")
    
    if webhook:
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(webhook)
                return {"status": "Webhook triggered", "code": res.status_code}
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": str(e)})
    return {"status": "No webhook configured"}

@app.post("/api/test_model")
async def test_model(request: Request):
    from google import genai
    from google.genai import types
    data = await request.json()
    api_key = data.get("gemini_api_key")
    ai_model = data.get("ai_model") # Can be empty now
    
    if not api_key:
        return JSONResponse(status_code=400, content={"error": "Vul eerst een API Key in."})
        
    errs = []
    # Try both v1 and v1beta
    for version in ["v1", "v1beta"]:
        try:
            client = genai.Client(api_key=api_key, http_options={'api_version': version})
            
            # Step 1: Just try to list models to validate the Key
            available = [m.name.replace("models/", "") for m in client.models.list() if "generateContent" in m.supported_generation_methods]
            
            if available:
                # Key is valid! 
                result_msg = f"API Key is GELDIG (via {version})."
                
                # Step 2: If the user already had a model selected, try a quick test
                if ai_model:
                    try:
                        ai_model_clean = ai_model.replace("models/", "")
                        res = client.models.generate_content(
                            model=ai_model_clean,
                            contents="Respond with 'OK'"
                        )
                        result_msg += f" Model '{ai_model_clean}' reageert ook correct."
                    except Exception as ge:
                        result_msg += f" Waarschuwing: Gekozen model '{ai_model}' gaf fout: {str(ge)}"
                
                return {
                    "result": result_msg,
                    "models": available
                }
        except Exception as e:
            errs.append(f"{version}: {str(e)}")
            
    return JSONResponse(status_code=400, content={
        "error": f"Kan geen verbinding maken. Controleer je API Key. Fouten: {'; '.join(errs)}"
    })

@app.get("/api/models")
async def get_available_models():
    from google import genai
    settings = get_settings()
    api_key = settings.get("gemini_api_key")
    if not api_key:
        return {"models": []}
        
    for version in ["v1", "v1beta"]:
        try:
            client = genai.Client(api_key=api_key, http_options={'api_version': version})
            models = [m.name.replace("models/", "") for m in client.models.list() if "generateContent" in m.supported_generation_methods]
            if models:
                return {"models": models, "version": version}
        except:
            continue
    return {"models": []}

@app.post("/api/restore_backup")
async def restore_backup(request: Request):
    import shutil
    data = await request.json()
    bak_file = data.get("bak_file")
    if not bak_file or not bak_file.endswith(".bak"):
        return JSONResponse(status_code=400, content={"error": "Invalid backup file"})
        
    original_target = bak_file[:-4] # removes .bak
    if os.path.exists(bak_file):
        shutil.copy2(bak_file, original_target)
        return {"status": "restored"}
    return JSONResponse(status_code=404, content={"error": "Backup file not found"})

# --- Serve Frontend SPA ---
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
else:
    @app.get("/")
    def index():
        return {"error": "Frontend not built yet. Run npm run build in /frontend and restart."}
