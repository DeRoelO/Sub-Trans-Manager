import os
import re
import time
import asyncio
from datetime import datetime
from core.config import get_settings

# Simple in-memory flag for stopping batch gracefully
_BATCH_IS_RUNNING = False
_BATCH_LOGS = []

def truncate_logs():
    global _BATCH_LOGS
    if len(_BATCH_LOGS) > 1000:
        _BATCH_LOGS = _BATCH_LOGS[-1000:]

def append_log(message: str):
    global _BATCH_LOGS
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{ts}] {message}"
    print(formatted)
    _BATCH_LOGS.append(formatted)
    truncate_logs()

def stop_batch_job():
    global _BATCH_IS_RUNNING
    if _BATCH_IS_RUNNING:
        _BATCH_IS_RUNNING = False
        append_log("🔴 STOP signal sent. Batch job will terminate after current item.")

def start_batch_job():
    global _BATCH_IS_RUNNING
    if _BATCH_IS_RUNNING:
        append_log("⚠️ Batch job is already running.")
        return
        
    _BATCH_IS_RUNNING = True
    append_log("🟢 Starting batch translation job...")
    
    settings = get_settings()
    media_paths = [settings.get("films_path", "/Films"), settings.get("series_path", "/Series")]
    limit = settings.get("batch_limit", 60)
    delay = settings.get("batch_delay", 60)
    
    # We load translator here to avoid circular imports during startup if any
    from core.translator import translate_single_file
    
    count = 0
    total_found = 0
    
    try:
        for base_path in media_paths:
            if not _BATCH_IS_RUNNING or count >= limit: break
            
            if not os.path.exists(base_path):
                append_log(f"⚠️ Directory {base_path} not found.")
                continue
                
            for root, dirs, files in os.walk(base_path):
                if not _BATCH_IS_RUNNING or count >= limit: break
                
                for file in files:
                    if not _BATCH_IS_RUNNING or count >= limit: break
                    
                    file_lower = file.lower()
                    if file_lower.endswith(".srt") and not any(x in file_lower for x in [".nl.", ".dut."]):
                        if any(x in file_lower for x in [".en.", ".eng.", ".hi.", ".en.hi.", ".eng.hi."]):
                            total_found += 1
                            en_path = os.path.join(root, file)
                            nl_path = re.sub(r'\.(en|eng|hi|en\.hi|eng\.hi)\.srt$', '.nl.srt', en_path, flags=re.IGNORECASE)
                            
                            if not os.path.exists(nl_path):
                                append_log(f"Processing: {file}")
                                success = translate_single_file(en_path, log_callback=append_log)
                                if success:
                                    count += 1
                                    if count < limit and _BATCH_IS_RUNNING:
                                        append_log(f"Waiting {delay} seconds before next file...")
                                        # Use standard time.sleep since background task runs in a separate thread via FastAPI BackgroundTasks
                                        for _ in range(delay):
                                            if not _BATCH_IS_RUNNING: break
                                            time.sleep(1)
                                else:
                                    append_log(f"❌ Failed to process {file}")
    except Exception as e:
        append_log(f"🔥 Error during batch processing: {e}")
    finally:
        _BATCH_IS_RUNNING = False
        append_log(f"🏁 Batch run complete. Translated {count} items.")

def get_batch_status():
    return {
        "is_running": _BATCH_IS_RUNNING
    }

async def get_log_generator(request):
    """Generator for Server-Sent Events (SSE) to stream logs"""
    last_idx = 0
    while True:
        if await request.is_disconnected():
            break
            
        current_len = len(_BATCH_LOGS)
        if current_len > last_idx:
            # Send all new logs
            for idx in range(last_idx, current_len):
                yield {"data": _BATCH_LOGS[idx]}
            last_idx = current_len
        elif _BATCH_IS_RUNNING:
            # Send a ping if nothing is happening just to keep connection alive
            yield {"data": ""} 
            
        await asyncio.sleep(1)
