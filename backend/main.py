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
from core.utils import is_dutch_variant, detect_is_wrong_language

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
                for file in files:
                    file_lower = file.lower()
                    if file_lower.endswith(".srt"):
                        # Extract base name by removing .srt and any language/modifier tags
                        # This regex matches .[lang].srt, .[lang].[hi/sdh/forced].srt, etc.
                        # We use a broad match for the language tag unless it's Dutch
                        
                        # Step 1: Detect if it's Dutch
                        is_nl = is_dutch_variant(file)
                        
                        # Step 2: Try to extract a base name
                        # We look for the LAST occurrence of a language-like tag
                        base_name_match = re.sub(r'\.[a-z]{2,5}(\.[a-z]{2,8})?\.srt$', '', file, flags=re.IGNORECASE)
                        if base_name_match == file:
                            base_name_match = file.replace(".srt", "")
                            
                        full_base_path = os.path.join(root, base_name_match)
                        
                        existing = next((m for m in media if m["base_path"] == full_base_path), None)
                        if not existing:
                            rel_path = os.path.relpath(root, start=path)
                            if kind == "series" and rel_path != ".":
                                display_dir = rel_path.split(os.sep)[0]
                            else:
                                display_dir = rel_path if rel_path != "." else os.path.basename(root)

                            existing = {
                                "base_path": full_base_path,
                                "name": base_name_match, 
                                "group": display_dir, 
                                "subpath": rel_path if rel_path != display_dir else "",
                                "kind": kind,
                                "has_en": False, # We keep 'has_en' for frontend compatibility but it means 'has_source'
                                "has_nl": False,
                                "has_bak": False,
                                "en_file": None,
                                "nl_file": None,
                                "bak_file": None
                            }
                            media.append(existing)
                        
                        if is_nl:
                            existing["has_nl"] = True
                            existing["nl_file"] = os.path.join(root, file)
                        else:
                            # Any non-Dutch SRT is a potential source
                            # If we already have a source, we might want to prioritize .en. or similar, 
                            # but for now let's just take the first one or prioritize if it has a tag
                            is_tagged = re.search(r'\.[a-z]{2,3}\.srt$', file_lower)
                            if not existing["has_en"] or is_tagged:
                                existing["has_en"] = True
                                existing["en_file"] = os.path.join(root, file)
                        
                        # Check for backups
                        bak_path = os.path.join(root, file) + ".bak"
                        if os.path.exists(bak_path):
                            existing["has_bak"] = True
                            existing["bak_file"] = bak_path
                            
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
    import google.generativeai as genai
    data = await request.json()
    api_key = data.get("gemini_api_key")
    ai_model = data.get("ai_model", "gemini-2.0-flash")
    
    if not api_key:
        return JSONResponse(status_code=400, content={"error": "Vul eerst een API Key in."})
        
    try:
        genai.configure(api_key=api_key)
        # Just listing models is the best way to test the key
        available = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                available.append(m.name.replace("models/", ""))
        
        if not available:
            return JSONResponse(status_code=400, content={"error": "API Key is geldig, maar geen modellen gevonden voor dit project."})
            
        result_msg = "API Key is GELDIG."
        
        # Optional: test specific model if provided
        if ai_model:
            try:
                model = genai.GenerativeModel(ai_model)
                res = model.generate_content("Respond with 'OK'")
                result_msg += f" Model '{ai_model}' reageert ook correct."
            except Exception as ge:
                result_msg += f" Waarschuwing: Model '{ai_model}' gaf een fout (mogelijk niet beschikbaar): {str(ge)}"
        
        return {
            "result": result_msg,
            "models": available
        }
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": f"Verbinding mislukt: {str(e)}"})

@app.get("/api/models")
async def get_available_models():
    import google.generativeai as genai
    settings = get_settings()
    api_key = settings.get("gemini_api_key")
    if not api_key:
        return {"models": []}
        
    try:
        genai.configure(api_key=api_key)
        models = [m.name.replace("models/", "") for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        return {"models": models}
    except:
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

@app.get("/api/audit/untagged")
async def audit_untagged():
    settings = get_settings()
    films_path = settings.get("films_path", "/Films")
    series_path = settings.get("series_path", "/Series")
    
    results = []
    for path in [films_path, series_path]:
        if os.path.exists(path):
            for root, dirs, files in os.walk(path):
                for file in files:
                    if file.lower().endswith(".srt"):
                        # Check if it has a language tag (e.g. .en.srt, .nl.srt)
                        # We consider it untagged if there's no tag or only generic tags like .hi. or .sdh.
                        if not re.search(r'\.[a-z]{2,3}(\.[a-z]{2,8})?\.srt$', file, flags=re.IGNORECASE):
                            full_path = os.path.join(root, file)
                            results.append({
                                "name": file,
                                "path": full_path,
                                "rel_path": os.path.relpath(full_path, start=path)
                            })
    return {"files": results}

@app.post("/api/audit/identify")
async def audit_identify(request: Request):
    import google.generativeai as genai
    data = await request.json()
    file_path = data.get("file_path")
    if not file_path or not os.path.exists(file_path):
        return JSONResponse(status_code=404, content={"error": "File not found"})
        
    settings = get_settings()
    api_key = settings.get("gemini_api_key")
    if not api_key:
        return JSONResponse(status_code=400, content={"error": "API Key missing"})
        
    try:
        with open(file_path, "rb") as f:
            bytes_data = f.read(5000)
        encoding = detect_encoding(bytes_data) or 'utf-8'
        sample_text = bytes_data.decode(encoding, errors='ignore')
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(settings.get("ai_model", "gemini-1.5-flash"))
        
        prompt = (
            "Identify the language of the following subtitle text. "
            "Return ONLY the ISO 639-1 language code (e.g. 'en', 'nl', 'fr', 'de', 'es').\n\n"
            f"[TEXT]\n{sample_text[:1000]}"
        )
        res = model.generate_content(prompt)
        lang_code = res.text.strip().lower()
        # Basic validation: should be 2 characters
        if len(lang_code) > 2:
            # Try to find a 2-char code in the response
            match = re.search(r'\b([a-z]{2})\b', lang_code)
            if match: lang_code = match.group(1)
            else: lang_code = "unknown"
            
        return {"language": lang_code}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/audit/rename")
async def audit_rename(request: Request):
    data = await request.json()
    file_path = data.get("file_path")
    lang_code = data.get("language")
    
    if not file_path or not lang_code or not os.path.exists(file_path):
        return JSONResponse(status_code=400, content={"error": "Invalid request"})
        
    new_path = file_path.replace(".srt", f".{lang_code}.srt")
    try:
        os.rename(file_path, new_path)
        return {"status": "success", "new_path": new_path}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/audit/list")
async def audit_list():
    settings = get_settings()
    films_path = settings.get("films_path", "/Films")
    series_path = settings.get("series_path", "/Series")
    target_lang = settings.get("target_language", "Dutch").lower()
    
    # Define tags to look for based on target language
    lang_map = {
        "dutch": [".nl.srt", ".dut.srt"],
        "english": [".en.srt", ".eng.srt"],
        "french": [".fr.srt", ".fre.srt", ".fra.srt"],
        "german": [".de.srt", ".ger.srt", ".deu.srt"],
        "spanish": [".es.srt", ".spa.srt"]
    }
    
    # Fallback to .nl.srt if not in map, or use the map
    valid_extensions = lang_map.get(target_lang, [".nl.srt"])
    
    results = []
    for path in [films_path, series_path]:
        if os.path.exists(path):
            for root, dirs, files in os.walk(path):
                for file in files:
                    file_lower = file.lower()
                    if any(file_lower.endswith(ext) for ext in valid_extensions):
                        full_path = os.path.join(root, file)
                        is_suspicious = detect_is_wrong_language(full_path, target_lang)
                        results.append({
                            "name": file,
                            "path": full_path,
                            "rel_path": os.path.relpath(full_path, start=path),
                            "is_suspicious": is_suspicious
                        })
    return {"files": results}

@app.post("/api/audit/delete_suspicious")
async def audit_delete_suspicious(request: Request):
    data = await request.json()
    paths = data.get("paths", [])
    deleted_count = 0
    for p in paths:
        if os.path.exists(p):
            os.remove(p)
            deleted_count += 1
    return {"status": "success", "count": deleted_count}

@app.get("/api/audit/sample")
async def audit_sample(file_path: str):
    if not os.path.exists(file_path):
        return JSONResponse(status_code=404, content={"error": "File not found"})
    
    try:
        with open(file_path, "rb") as f:
            bytes_data = f.read()
        encoding = detect_encoding(bytes_data) or 'utf-8'
        content = bytes_data.decode(encoding, errors='ignore')
        parsed = parse_srt(content)
        
        import random
        # Get 10 random samples or all if less than 10
        sample_size = min(len(parsed), 10)
        samples = random.sample(parsed, sample_size)
        return {"samples": sorted(samples, key=lambda x: int(x['index']))}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/audit/delete")
async def audit_delete(request: Request):
    data = await request.json()
    file_path = data.get("file_path")
    if not file_path or not os.path.exists(file_path):
        return JSONResponse(status_code=404, content={"error": "File not found"})
    
    try:
        os.remove(file_path)
        return {"status": "deleted"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# --- Serve Frontend SPA ---
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
else:
    @app.get("/")
    def index():
        return {"error": "Frontend not built yet. Run npm run build in /frontend and restart."}
