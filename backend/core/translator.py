import os
import re
import json
import time
from typing import List, Dict
import google.generativeai as genai
from google.api_core import exceptions
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from core.utils import detect_encoding, verify_language_ai, is_target_language_file

from collections import deque

# Session tracking for success rate (sliding window of last 50 calls)
_CALL_HISTORY = deque(maxlen=50)

def get_success_rate():
    if not _CALL_HISTORY: return 1.0
    return sum(1 for x in _CALL_HISTORY if x) / len(_CALL_HISTORY)

def parse_srt(content: str) -> List[Dict[str, str]]:
    pattern = re.compile(r'(\d+)\s*\n(\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3})\s*\n((?:.|\n)*?)(?=\n\d+\s*\n|\Z)', re.MULTILINE)
    return [{'index': m[0], 'time': m[1], 'text': m[2].strip()} for m in pattern.findall(content)]

def chunk_text(parsed_data: List[Dict[str, str]], chunk_size: int = 2000) -> List[List[Dict[str, str]]]:
    chunks, current_chunk, current_length = [], [], 0
    for item in parsed_data:
        text_len = len(item['text'])
        if current_length + text_len > chunk_size:
            chunks.append(current_chunk)
            current_chunk, current_length = [], 0
        current_chunk.append(item)
        current_length += text_len
    if current_chunk: chunks.append(current_chunk)
    return chunks

def translate_chunk(model, texts: List[str], target_language: str) -> List[str]:
    input_json = json.dumps({"items": [{"id": i, "text": t} for i, t in enumerate(texts)]}, ensure_ascii=False)
    
    safety = { 
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE, 
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE, 
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE, 
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE 
    }
    
    for attempt in range(3): # Increased attempts for retry logic
        try:
            temp = 0.1 if attempt == 0 else 0.3
            prompt = (
                f"Translate the 'text' fields in the JSON to natural and informal {target_language}. "
                "Use context from surrounding lines. Output ONLY JSON.\n"
                f"[INPUT]\n{input_json}"
            )
            
            res = model.generate_content(
                prompt, 
                safety_settings=safety, 
                generation_config={"temperature": temp}
            )
            
            start_idx = res.text.find('{')
            end_idx = res.text.rfind('}')
            if start_idx == -1 or end_idx == -1: raise ValueError("JSON not found")
            
            clean_json = res.text[start_idx : end_idx + 1]
            items_dict = json.loads(clean_json)
            items = []
            for k, v in items_dict.items():
                if isinstance(v, list): items = v; break
            
            if not items: raise ValueError("No items in JSON")
                
            results = [next((i.get("text", "") for i in items if i.get("id") == idx), texts[idx]) for idx in range(len(texts))]
            
            # Validation: check if it actually translated something
            identical_count = sum(1 for i, t in enumerate(results) if t.strip() == texts[i].strip())
            if identical_count > (len(texts) * 0.8) and len(texts) > 2:
                raise ValueError("Source text returned")

            _CALL_HISTORY.append(True)
            return results

        except exceptions.ServiceUnavailable:
            # 503 or high demand error
            print("⚠️ Model high demand (503). Waiting 5 seconds...")
            time.sleep(5)
            continue
        except Exception as e:
            print(f"⚠️ Chunk translation error (Attempt {attempt+1}): {e}")
            if attempt < 2: time.sleep(2)
            else: 
                _CALL_HISTORY.append(False)
                return texts

def translate_single_file(input_file: str, log_callback=None):
    if log_callback: log_callback(f"Starting translation for {input_file}")
    
    from core.config import get_settings
    settings = get_settings()
    api_key = settings.get("gemini_api_key")
    if not api_key: return False

    ai_model_name = settings.get("ai_model", "gemini-1.5-flash")
    target_language = settings.get("target_language", "Dutch")
    target_lang_tag = settings.get("target_language_tag", "nl")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(ai_model_name)
    
    with open(input_file, 'rb') as f: bytes_data = f.read()
    encoding = detect_encoding(bytes_data) or 'utf-8'
    content = bytes_data.decode(encoding, errors='ignore')
    
    parsed = parse_srt(content)
    all_results = []
    chunks = chunk_text(parsed, chunk_size=2000) # 5x smaller chunks
    total_chunks = len(chunks)
    
    for idx, chunk in enumerate(chunks):
        # Check Success Rate (only after we have at least 10 calls to avoid early spikes)
        rate = get_success_rate()
        if len(_CALL_HISTORY) >= 10 and rate < 0.90:
            if log_callback: log_callback(f"⛔ Success rate dropped to {rate:.1%}. Pausing for 1 hour...")
            time.sleep(3600)
            _CALL_HISTORY.clear()

        res = translate_chunk(model, [item['text'] for item in chunk], target_language)
        all_results.append(res)
        if log_callback: log_callback(f"Chunk {idx + 1}/{total_chunks} done. (Success Rate: {get_success_rate():.1%})")
        time.sleep(0.5)
        
    flat_translations = [t for chunk in all_results for t in chunk]
    final_srt = "\n".join([f"{o['index']}\n{o['time']}\n{flat_translations[i] if i < len(flat_translations) else o['text']}\n" for i, o in enumerate(parsed)])
    
    output_path = re.sub(r'\.[a-z]{2,5}(\.[a-z]{2,8})?\.srt$', f'.{target_lang_tag}.srt', input_file, flags=re.IGNORECASE)
    if output_path == input_file: output_path = input_file.replace(".srt", f".{target_lang_tag}.srt")
        
    try:
        import shutil
        shutil.copy2(input_file, input_file + ".bak")
        if os.path.exists(output_path): shutil.copy2(output_path, output_path + ".bak")
    except: pass

    with open(output_path, 'w', encoding='utf-8') as f: f.write(final_srt)
    if log_callback: log_callback(f"Saved: {output_path}")

    # Trigger Webhook
    webhook = settings.get("jellyfin_webhook")
    if webhook:
        try:
            import httpx
            httpx.post(webhook)
        except: pass

    return True
