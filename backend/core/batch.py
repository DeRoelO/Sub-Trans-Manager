import os
import re
import time
import asyncio
from datetime import datetime
from core.config import get_settings
from core.utils import is_target_language_file

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
    target_tag = settings.get("target_language_tag", "nl")
    
    from core.translator import translate_single_file
    
    count = 0
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
                    
                    if file.lower().endswith(".srt"):
                        # Skip if it's already the target language
                        if is_target_language_file(file):
                            continue
                        
                        # Check if it has a source tag (broadly .[lang].srt) or no tag
                        # We'll prioritize tagged files as sources
                        is_tagged = re.search(r'\.[a-z]{2,5}(\.[a-z]{2,8})?\.srt$', file, flags=re.IGNORECASE)
                        
                        source_path = os.path.join(root, file)
                        # Predict target path
                        target_path = re.sub(r'\.[a-z]{2,5}(\.[a-z]{2,8})?\.srt$', f'.{target_tag}.srt', source_path, flags=re.IGNORECASE)
                        if target_path == source_path:
                            target_path = source_path.replace(".srt", f".{target_tag}.srt")
                        
                        if not os.path.exists(target_path):
                            append_log(f"Processing: {file}")
                            success = translate_single_file(source_path, log_callback=append_log)
                            if success:
                                count += 1
                                if count < limit and _BATCH_IS_RUNNING:
                                    append_log(f"Waiting {delay} seconds before next file...")
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
    from core.config import get_settings
    from core.utils import detect_encoding
    import google.generativeai as genai
    import os
    import re

    settings = get_settings()
    api_key = settings.get('gemini_api_key')
    if not api_key:
        if log_callback: log_callback('? Error: API Key missing for bulk renaming.')
        return

    # 1. Find untagged files
    films_path = settings.get('films_path', '/Films')
    series_path = settings.get('series_path', '/Series')
    untagged = []
    for path in [films_path, series_path]:
        if os.path.exists(path):
            for root, dirs, files in os.walk(path):
                for file in files:
                    if file.lower().endswith('.srt') and not re.search(r'\.[a-z]{2,5}(\.[a-z]{2,8})?\.srt$', file, flags=re.IGNORECASE):
                        untagged.append(os.path.join(root, file))

    if not untagged:
        if log_callback: log_callback('? No untagged files found.')
        return

    if log_callback: log_callback(f'?? Starting bulk rename of {len(untagged)} untagged files...')

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(settings.get('ai_model', 'gemini-1.5-flash'))

    success_count = 0
    for i, file_path in enumerate(untagged):
        try:
            # Identify
            with open(file_path, 'rb') as f: bytes_data = f.read(5000)
            encoding = detect_encoding(bytes_data) or 'utf-8'
            sample_text = bytes_data.decode(encoding, errors='ignore')
            
            prompt = 'Identify the language of this subtitle text. Return ONLY the ISO 639-1 code (e.g. en, nl).\n\n' + sample_text[:1000]
            res = model.generate_content(prompt)
            lang_code = res.text.strip().lower()
            match = re.search(r'\b([a-z]{2})\b', lang_code)
            lang_code = match.group(1) if match else None

            if lang_code:
                new_path = file_path.replace('.srt', f'.{lang_code}.srt')
                os.rename(file_path, new_path)
                success_count += 1
                if log_callback: log_callback(f'[{i+1}/{len(untagged)}] Renamed: {os.path.basename(file_path)} -> .{lang_code}.srt')
            else:
                if log_callback: log_callback(f'[{i+1}/{len(untagged)}] ?? Could not identify: {os.path.basename(file_path)}')
            
            # Small delay to respect API limits
            await asyncio.sleep(0.5)
        except Exception as e:
            if log_callback: log_callback(f'? Error identifying {os.path.basename(file_path)}: {e}')

    if log_callback: log_callback(f'?? Bulk rename complete. {success_count} files renamed.')
