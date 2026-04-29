import os
import re
import time
import asyncio
from datetime import datetime
from core.config import get_settings
from core.utils import is_target_language_file, detect_is_wrong_language, detect_encoding, heuristic_detect_language

# Simple in-memory flag for stopping batch gracefully
_BATCH_IS_RUNNING = False
_BATCH_LOGS = []

def truncate_logs():
    global _BATCH_LOGS
    if len(_BATCH_LOGS) > 1000:
        _BATCH_LOGS = _BATCH_LOGS[-1000:]

def clear_logs():
    global _BATCH_LOGS
    _BATCH_LOGS = []
    append_log("🗑️ Logs cleared.")

def append_log(message: str):
    global _BATCH_LOGS
    ts = datetime.now().strftime("%H:%M:%S")
    formatted = f"[{ts}] {message}"
    print(formatted)
    _BATCH_LOGS.append(formatted)
    truncate_logs()

def stop_batch_job():
    global _BATCH_IS_RUNNING
    if _BATCH_IS_RUNNING:
        _BATCH_IS_RUNNING = False
        append_log("🔴 STOP signal sent. Terminating after current item.")

async def identify_untagged_files(log_callback=None):
    """Heuristic identification (FREE - No API calls)."""
    settings = get_settings()
    films_path = settings.get('films_path', '/Films')
    series_path = settings.get('series_path', '/Series')
    
    untagged = []
    for path in [films_path, series_path]:
        if os.path.exists(path):
            for root, dirs, files in os.walk(path):
                for file in files:
                    if file.lower().endswith('.srt') and not re.search(r'\.[a-z]{2,5}(\.[a-z]{2,8})?\.srt$', file, flags=re.IGNORECASE):
                        untagged.append(os.path.join(root, file))

    if not untagged: return

    if log_callback: log_callback(f"🔍 Analyzing {len(untagged)} untagged files using heuristics...")

    success_count = 0
    for file_path in untagged:
        if not _BATCH_IS_RUNNING: break
        try:
            with open(file_path, 'rb') as f: bytes_data = f.read(15000)
            encoding = detect_encoding(bytes_data) or 'utf-8'
            text = bytes_data.decode(encoding, errors='ignore')
            
            lang_code = heuristic_detect_language(text)
            if lang_code != "unknown":
                new_path = file_path.replace('.srt', f'.{lang_code}.srt')
                os.rename(file_path, new_path)
                success_count += 1
                if log_callback: log_callback(f"🏷️ Identified: {os.path.basename(file_path)} -> .{lang_code}.srt")
        except: pass

    if success_count > 0 and log_callback:
        log_callback(f"✅ Successfully identified {success_count} files.")

async def cleanup_suspicious_files(log_callback=None):
    settings = get_settings()
    films_path = settings.get('films_path', '/Films')
    series_path = settings.get('series_path', '/Series')
    target_lang = settings.get('target_language', 'Dutch')
    variants = settings.get('target_language_variants', ['nl', 'dut'])
    
    count = 0
    for path in [films_path, series_path]:
        if os.path.exists(path):
            for root, dirs, files in os.walk(path):
                for file in files:
                    if not _BATCH_IS_RUNNING: break
                    file_lower = file.lower()
                    if any(f".{v}." in file_lower or file_lower.endswith(f".{v}.srt") for v in variants):
                        full_path = os.path.join(root, file)
                        if detect_is_wrong_language(full_path, target_lang):
                            os.remove(full_path)
                            count += 1
                            if log_callback: log_callback(f"🗑️ Deleted suspicious translation: {file}")
    if count > 0 and log_callback:
        log_callback(f"🧹 Cleaned up {count} suspicious translations.")

async def start_batch_job():
    global _BATCH_IS_RUNNING
    if _BATCH_IS_RUNNING:
        append_log("⚠️ Batch job is already running.")
        return
        
    _BATCH_IS_RUNNING = True
    append_log("🟢 Starting automated batch job...")
    
    settings = get_settings()
    media_paths = [settings.get("films_path", "/Films"), settings.get("series_path", "/Series")]
    limit = settings.get("batch_limit", 60)
    delay = settings.get("batch_delay", 60)
    target_tag = settings.get("target_language_tag", "nl")
    
    try:
        # Step 1: Identify Untagged (Heuristic - Free)
        if settings.get("auto_identify_untagged", True):
            await identify_untagged_files(log_callback=append_log)

        # Step 2: Cleanup Suspicious (Heuristic - Free)
        if settings.get("auto_cleanup_suspicious", False):
            await cleanup_suspicious_files(log_callback=append_log)

        # Step 3: Translation Loop
        from core.translator import translate_single_file
        count = 0
        for base_path in media_paths:
            if not _BATCH_IS_RUNNING or count >= limit: break
            if not os.path.exists(base_path): continue
                
            for root, dirs, files in os.walk(base_path):
                if not _BATCH_IS_RUNNING or count >= limit: break
                for file in files:
                    if not _BATCH_IS_RUNNING or count >= limit: break
                    if file.lower().endswith(".srt"):
                        if is_target_language_file(file): continue
                        
                        source_path = os.path.join(root, file)
                        target_path = re.sub(r'\.[a-z]{2,5}(\.[a-z]{2,8})?\.srt$', f'.{target_tag}.srt', source_path, flags=re.IGNORECASE)
                        if target_path == source_path:
                            target_path = source_path.replace(".srt", f".{target_tag}.srt")
                        
                        if not os.path.exists(target_path):
                            append_log(f"🚀 Processing: {file}")
                            success = translate_single_file(source_path, log_callback=append_log)
                            if success:
                                count += 1
                                if count < limit and _BATCH_IS_RUNNING:
                                    for _ in range(delay):
                                        if not _BATCH_IS_RUNNING: break
                                        await asyncio.sleep(1)
                            else:
                                append_log(f"❌ Failed to process {file}")
    except Exception as e:
        append_log(f"🔥 Error during batch processing: {e}")
    finally:
        _BATCH_IS_RUNNING = False
        append_log(f"🏁 Batch run complete. Translated {count} items.")

def get_batch_status():
    return {"is_running": _BATCH_IS_RUNNING}

async def get_log_generator(request):
    last_idx = 0
    while True:
        if await request.is_disconnected(): break
        current_len = len(_BATCH_LOGS)
        if current_len > last_idx:
            for idx in range(last_idx, current_len):
                yield {"data": _BATCH_LOGS[idx]}
            last_idx = current_len
        elif _BATCH_IS_RUNNING:
            yield {"data": ""} 
        await asyncio.sleep(1)

async def bulk_rename_untagged_task(log_callback=None):
    global _BATCH_IS_RUNNING
    if _BATCH_IS_RUNNING: return
    _BATCH_IS_RUNNING = True
    try:
        await identify_untagged_files(log_callback=log_callback)
    finally:
        _BATCH_IS_RUNNING = False
