import os
import re
import json
import time
from typing import List, Dict
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from core.utils import detect_encoding, verify_language_ai, is_target_language_file

def parse_srt(content: str) -> List[Dict[str, str]]:
    pattern = re.compile(r'(\d+)\s*\n(\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3})\s*\n((?:.|\n)*?)(?=\n\d+\s*\n|\Z)', re.MULTILINE)
    return [{'index': m[0], 'time': m[1], 'text': m[2].strip()} for m in pattern.findall(content)]

def chunk_text(parsed_data: List[Dict[str, str]], chunk_size: int = 10000) -> List[List[Dict[str, str]]]:
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
    
    for attempt in range(2):
        temp = 0.1 if attempt == 0 else 0.3
        force_msg = "" if attempt == 0 else "IMPORTANT: You previously failed or returned English. You MUST translate to the target language now! "
        
        prompt = (
            f"{force_msg}You are an expert movie and subtitle translator. "
            f"Translate the 'text' fields in the JSON object to natural and informal {target_language}. "
            "Use context from surrounding lines to ensure proper flow and tone. "
            "IMPORTANT: Avoid literal translations that sound unnatural. "
            "Ensure the 'id' remains identical. Output ONLY the JSON object.\n"
            f"[INPUT]\n{input_json}"
        )
        
        try:
            res = model.generate_content(
                prompt, 
                safety_settings=safety, 
                generation_config={"temperature": temp}
            )
            start_idx = res.text.find('{')
            end_idx = res.text.rfind('}')
            if start_idx == -1 or end_idx == -1:
                raise ValueError("JSON not found in response")
            
            clean_json = res.text[start_idx : end_idx + 1]
            items_dict = json.loads(clean_json)
            items = []
            for k, v in items_dict.items():
                if isinstance(v, list):
                    items = v
                    break
            
            if not items:
                raise ValueError("Could not extract items array from JSON")
                
            results = [next((i.get("text", "") for i in items if i.get("id") == idx), texts[idx]) for idx in range(len(texts))]
            
            # Substantiality check: if too many items are identical to source, it likely failed to translate
            identical_count = sum(1 for i, t in enumerate(results) if t.strip() == texts[i].strip())
            if identical_count > (len(texts) * 0.7) and len(texts) > 2:
                if attempt == 0:
                    raise ValueError("Model returned source text instead of translation (80%+ identical)")

            return results
        except Exception as e:
            if attempt < 1: 
                time.sleep(2)
            else: 
                print(f"Translation chunk failed after {attempt+1} attempts. Error: {e}")
                return texts

def translate_single_file(input_file: str, log_callback=None):
    if log_callback: log_callback(f"Starting translation for {input_file}")
    
    API_KEY = os.environ.get("GEMINI_API_KEY")
    from core.config import get_settings
    settings = get_settings()
    
    if not API_KEY:
        API_KEY = settings.get("gemini_api_key")
        
    if not API_KEY:
        msg = f"ERROR: GEMINI_API_KEY missing for {input_file}"
        if log_callback: log_callback(msg)
        return False

    ai_model_name = settings.get("ai_model", "gemini-1.5-flash")
    target_language = settings.get("target_language", "Dutch")
    target_lang_tag = settings.get("target_language_tag", "nl")

    if log_callback: log_callback(f"Model: {ai_model_name}, Target Language: {target_language} ({target_lang_tag})")
        
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel(ai_model_name)
    
    with open(input_file, 'rb') as f: bytes_data = f.read()
    encoding = detect_encoding(bytes_data) or 'utf-8'
    content = bytes_data.decode(encoding, errors='ignore')
    
    parsed = parse_srt(content)
    if log_callback: log_callback(f"Parsed {len(parsed)} blocks. Starting translation.")
    
    all_results = []
    chunks = chunk_text(parsed)
    total_chunks = len(chunks)
    
    for idx, chunk in enumerate(chunks):
        all_results.append(translate_chunk(model, [item['text'] for item in chunk], target_language))
        if log_callback: log_callback(f"Translated chunk {idx + 1}/{total_chunks}")
        time.sleep(1)
        
    flat_translations = [t for chunk in all_results for t in chunk]
    final_srt = "\n".join([f"{o['index']}\n{o['time']}\n{flat_translations[i] if i < len(flat_translations) else o['text']}\n" for i, o in enumerate(parsed)])
    
    # Generate output path using dynamic tag
    output_path = re.sub(r'\.[a-z]{2,5}(\.[a-z]{2,8})?\.srt$', f'.{target_lang_tag}.srt', input_file, flags=re.IGNORECASE)
    if output_path == input_file: 
        output_path = input_file.replace(".srt", f".{target_lang_tag}.srt")
        
    try:
        import shutil
        shutil.copy2(input_file, input_file + ".bak")
        if log_callback: log_callback(f"Source backup created: {input_file}.bak")
        if os.path.exists(output_path):
            shutil.copy2(output_path, output_path + ".bak")
            if log_callback: log_callback(f"Previous translation backup created.")
    except Exception as e:
        if log_callback: log_callback(f"Warning: Backup failed: {e}")

    with open(output_path, 'w', encoding='utf-8') as f: 
        f.write(final_srt)
        
    if log_callback: log_callback(f"File saved to {output_path}")

    # VERIFICATION
    if log_callback: log_callback(f"Verifying {target_language} quality...")
    is_valid = verify_language_ai(model, final_srt, target_language)
    if not is_valid:
        if log_callback: log_callback(f"WARNING: Verification failed. The output might not be primarily in {target_language}.")
    else:
        if log_callback: log_callback(f"Verification successful: File is in {target_language}.")
    
    webhook = settings.get("jellyfin_webhook")
    if webhook:
        try:
            import httpx
            httpx.post(webhook)
            if log_callback: log_callback("Webhook triggered.")
        except Exception as e:
            if log_callback: log_callback(f"Webhook failed: {e}")

    return True
