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

def get_batch_preview():
    """Generates a preview of what will be processed in the next batch run."""
    settings = get_settings()
    target_types = settings.get("batch_target_types", ["films", "series"])
    
    media_paths = []
    if "films" in target_types and settings.get("films_path") and os.path.exists(settings.get("films_path")):
        media_paths.append(("Films", settings.get("films_path")))
    if "series" in target_types and settings.get("series_path") and os.path.exists(settings.get("series_path")):
        media_paths.append(("Series", settings.get("series_path")))

    target_tag = settings.get("target_language_tag", "nl")
    variants = settings.get("target_language_variants", ["nl", "dut"])

    untagged_files = []
    to_translate = []
    target_files = []

    for kind, base_path in media_paths:
        for root, dirs, files in os.walk(base_path):
            for file in files:
                if not file.lower().endswith(".srt"):
                    continue
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, start=base_path)

                # Check if untagged (.srt without language extension)
                if not re.search(r'\.[a-z]{2,5}(\.[a-z]{2,8})?\.srt$', file, flags=re.IGNORECASE):
                    untagged_files.append({"name": file, "path": full_path, "rel_path": rel_path, "kind": kind})
                    continue

                # Check if it's already in the target language
                if is_target_language_file(file):
                    target_files.append({"name": file, "path": full_path, "rel_path": rel_path, "kind": kind})
                    continue

                # Check if target translation exists
                target_path = re.sub(r'\.[a-z]{2,5}(\.[a-z]{2,8})?\.srt$', f'.{target_tag}.srt', full_path, flags=re.IGNORECASE)
                if target_path == full_path:
                    target_path = full_path.replace(".srt", f".{target_tag}.srt")

                if not os.path.exists(target_path):
                    to_translate.append({
                        "name": file,
                        "path": full_path,
                        "target_path": target_path,
                        "rel_path": rel_path,
                        "kind": kind
                    })

    limit = settings.get("batch_limit", 60)

    return {
        "is_running": _BATCH_IS_RUNNING,
        "scope": {
            "target_types": target_types,
            "paths": [p[1] for p in media_paths],
            "limit": limit,
            "delay": settings.get("batch_delay", 5),
            "auto_identify": settings.get("auto_identify_untagged", True),
            "auto_cleanup": settings.get("auto_cleanup_suspicious", False),
            "auto_translate": settings.get("auto_translate_missing", True),
        },
        "untagged_count": len(untagged_files),
        "target_file_count": len(target_files),
        "total_to_translate": len(to_translate),
        "to_translate_preview": to_translate[:limit]
    }

async def identify_untagged_files_list(untagged_files: list, log_callback=None):
    """Heuristic identification (FREE - No API calls)."""
    if not untagged_files: return 0

    if log_callback: log_callback(f"🔍 Analyzing {len(untagged_files)} untagged files using heuristics...")

    success_count = 0
    for item in untagged_files:
        if not _BATCH_IS_RUNNING: break
        file_path = item["path"]
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
        except Exception as e:
            pass

    if success_count > 0 and log_callback:
        log_callback(f"✅ Successfully identified {success_count} untagged files.")
    return success_count

async def cleanup_suspicious_files_list(target_files: list, log_callback=None):
    settings = get_settings()
    target_lang = settings.get('target_language', 'Dutch')
    
    count = 0
    for item in target_files:
        if not _BATCH_IS_RUNNING: break
        full_path = item["path"]
        if detect_is_wrong_language(full_path, target_lang):
            try:
                os.remove(full_path)
                count += 1
                if log_callback: log_callback(f"🗑️ Deleted suspicious translation: {item['name']}")
            except: pass
            
    if count > 0 and log_callback:
        log_callback(f"🧹 Cleaned up {count} suspicious translations.")
    return count

async def start_batch_job():
    global _BATCH_IS_RUNNING
    if _BATCH_IS_RUNNING:
        append_log("⚠️ Batch job is already running.")
        return
        
    _BATCH_IS_RUNNING = True
    append_log("🟢 Starting automated batch job...")
    
    settings = get_settings()
    limit = settings.get("batch_limit", 60)
    delay = settings.get("batch_delay", 5)
    
    do_identify = settings.get("auto_identify_untagged", True)
    do_cleanup = settings.get("auto_cleanup_suspicious", False)
    do_translate = settings.get("auto_translate_missing", True)

    try:
        # Step 0: Single Pass Discovery
        append_log("🔍 [Batch] Scanning media directories...")
        preview = get_batch_preview()
        
        target_types = preview["scope"]["target_types"]
        append_log(f"📋 Scope: {', '.join(target_types).upper()} | Limit: {limit} | Delay: {delay}s")
        append_log(f"📊 Scan Results: {preview['untagged_count']} untagged, {preview['total_to_translate']} missing translations.")

        # Step 1: Identify Untagged (Heuristic - Free)
        if do_identify and preview["untagged_count"] > 0:
            append_log("📌 [Step 1/3] Identifying untagged files...")
            # Collect full untagged list
            untagged_list = []
            for path in preview["scope"]["paths"]:
                for root, dirs, files in os.walk(path):
                    for file in files:
                        if file.lower().endswith('.srt') and not re.search(r'\.[a-z]{2,5}(\.[a-z]{2,8})?\.srt$', file, flags=re.IGNORECASE):
                            untagged_list.append({"path": os.path.join(root, file)})
            await identify_untagged_files_list(untagged_list, log_callback=append_log)
        else:
            append_log("⏭️ [Step 1/3] Identify untagged skipped (Disabled or no untagged files).")

        # Step 2: Cleanup Suspicious (Heuristic - Free)
        if do_cleanup:
            append_log("📌 [Step 2/3] Checking for suspicious translations...")
            target_list = []
            variants = settings.get("target_language_variants", ["nl", "dut"])
            for path in preview["scope"]["paths"]:
                for root, dirs, files in os.walk(path):
                    for file in files:
                        if any(f".{v}." in file.lower() or file.lower().endswith(f".{v}.srt") for v in variants):
                            target_list.append({"name": file, "path": os.path.join(root, file)})
            await cleanup_suspicious_files_list(target_list, log_callback=append_log)
        else:
            append_log("⏭️ [Step 2/3] Cleanup suspicious skipped (Disabled).")

        # Step 3: Translation Loop
        if do_translate:
            append_log("📌 [Step 3/3] Translating missing subtitles...")
            from core.translator import translate_single_file
            
            queue = preview["to_translate_preview"]
            if not queue:
                append_log("🎉 No missing translations found! All media files are up-to-date.")
            else:
                append_log(f"🚀 Queued {len(queue)} items for translation.")
                count = 0
                for item in queue:
                    if not _BATCH_IS_RUNNING or count >= limit: break
                    source_path = item["path"]
                    append_log(f"🚀 Processing [{count + 1}/{len(queue)}]: {item['name']} ({item['kind']})")
                    
                    # Run sync translation in a separate thread to keep asyncio event loop responsive!
                    success = await asyncio.to_thread(translate_single_file, source_path, log_callback=append_log)
                    if success:
                        count += 1
                        if count < limit and _BATCH_IS_RUNNING and delay > 0:
                            append_log(f"⏳ Waiting {delay}s before next item...")
                            for _ in range(delay):
                                if not _BATCH_IS_RUNNING: break
                                await asyncio.sleep(1)
                    else:
                        append_log(f"❌ Failed to process {item['name']}")
                append_log(f"🏁 Translation completed. Translated {count} items.")
        else:
            append_log("⏭️ [Step 3/3] Auto-translate missing skipped (Disabled in settings).")

    except Exception as e:
        append_log(f"🔥 Error during batch processing: {e}")
    finally:
        _BATCH_IS_RUNNING = False
        append_log("🏁 Batch run finished.")

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
        preview = get_batch_preview()
        untagged_list = []
        for path in preview["scope"]["paths"]:
            for root, dirs, files in os.walk(path):
                for file in files:
                    if file.lower().endswith('.srt') and not re.search(r'\.[a-z]{2,5}(\.[a-z]{2,8})?\.srt$', file, flags=re.IGNORECASE):
                        untagged_list.append({"path": os.path.join(root, file)})
        await identify_untagged_files_list(untagged_list, log_callback=log_callback)
    finally:
        _BATCH_IS_RUNNING = False
