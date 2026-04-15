import os
import re
import json
import time
import chardet
from typing import List, Dict, Any
from google import genai
from google.genai import types

def detect_encoding(file_byte: bytes) -> str:
    return chardet.detect(file_byte)['encoding']

def parse_srt(content: str) -> List[Dict[str, str]]:
    pattern = re.compile(r'(\d+)\s*\n(\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3})\s*\n((?:.|\n)*?)(?=\n\d+\s*\n|\Z)', re.MULTILINE)
    return [{'index': m[0], 'time': m[1], 'text': m[2].strip()} for m in pattern.findall(content)]

def chunk_text(parsed_data: List[Dict[str, str]], chunk_size: int = 1500) -> List[List[Dict[str, str]]]:
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

def translate_chunk(client, model_name: str, texts: List[str], target_language: str) -> List[str]:
    input_json = json.dumps({"items": [{"id": i, "text": t} for i, t in enumerate(texts)]}, ensure_ascii=False)
    prompt = (
        f"Translate the 'text' field in the following JSON objects to {target_language}. "
        "Keep the 'id' intact. Use informal phrasing (e.g., 'je/jou' for Dutch). "
        "IMPORTANT: NEVER output the source language. You MUST translate the text, even if it seems hard. "
        "Output ONLY valid JSON matching the input structure.\n"
        f"[INPUT]\n{input_json}"
    )
    
    safety = [
        types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
        types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=types.HarmBlockThreshold.BLOCK_NONE),
        types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
        types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=types.HarmBlockThreshold.BLOCK_NONE)
    ]
    
    config = types.GenerateContentConfig(
        temperature=0.1,
        safety_settings=safety
    )

    for attempt in range(2):
        try:
            res = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config
            )
            start_idx = res.text.find('{')
            end_idx = res.text.rfind('}')
            if start_idx == -1 or end_idx == -1:
                raise ValueError("JSON not found in response")
            
            clean_json = res.text[start_idx : end_idx + 1]
            items_dict = json.loads(clean_json)
            # Find the array of objects, handling different potential keys from the AI
            items = []
            for k, v in items_dict.items():
                if isinstance(v, list):
                    items = v
                    break
            
            if not items:
                raise ValueError("Could not extract items array from JSON")
                
            return [next((i.get("text", "") for i in items if i.get("id") == idx), texts[idx]) for idx in range(len(texts))]
        except Exception as e:
            if attempt < 1: 
                time.sleep(2)
            else: 
                print(f"Translation chunk failed after 2 attempts. Returning original text. Error: {e}")
                return texts

def translate_single_file(input_file: str, log_callback=None):
    if log_callback: log_callback(f"Starting translation for {input_file}")
    
    API_KEY = os.environ.get("GEMINI_API_KEY")
    settings = None
    if not API_KEY:
        from core.config import get_settings
        settings = get_settings()
        API_KEY = settings.get("gemini_api_key")
        
    if not API_KEY:
        msg = f"ERROR: GEMINI_API_KEY could not be found for {input_file}"
        if log_callback: log_callback(msg)
        print(msg)
        return False
        
    if not settings:
        from core.config import get_settings
        settings = get_settings()

    ai_model_name = settings.get("ai_model", "gemini-1.5-flash")
    target_language = settings.get("target_language", "Dutch")

    if log_callback: log_callback(f"[HANDMATIG] Using model: {ai_model_name}, Target: {target_language}")
        
    client = genai.Client(api_key=API_KEY)
    
    with open(input_file, 'rb') as f: bytes_data = f.read()
    encoding = detect_encoding(bytes_data) or 'utf-8'
    content = bytes_data.decode(encoding, errors='ignore')
    
    parsed = parse_srt(content)
    
    if log_callback: log_callback(f"Parsed {len(parsed)} subtitle blocks. Beginning chunked translation.")
    
    all_results = []
    chunks = chunk_text(parsed)
    total_chunks = len(chunks)
    
    for idx, chunk in enumerate(chunks):
        all_results.append(translate_chunk(client, ai_model_name, [item['text'] for item in chunk], target_language))
        if log_callback: log_callback(f"Translated chunk {idx + 1}/{total_chunks}")
        time.sleep(1)
        
    flat_translations = [t for chunk in all_results for t in chunk]
    
    # Catch any length mismatch
    if len(flat_translations) != len(parsed):
        if log_callback: log_callback(f"WARNING: translation length mismatch! Expected {len(parsed)}, got {len(flat_translations)}.")
        
    final_srt = "\n".join([f"{o['index']}\n{o['time']}\n{flat_translations[i] if i < len(flat_translations) else o['text']}\n" for i, o in enumerate(parsed)])
    
    
    # Save a backup of the original input file
    try:
        import shutil
        shutil.copy2(input_file, input_file + ".bak")
        if log_callback: log_callback(f"Backup created: {input_file}.bak")
    except Exception as e:
        if log_callback: log_callback(f"Warning: Failed to create backup: {e}")

    output_path = re.sub(r'\.(en|eng|hi|en\.hi|eng\.hi)\.srt$', '.nl.srt', input_file, flags=re.IGNORECASE)
    if output_path == input_file: 
        output_path = input_file.replace(".srt", ".nl.srt")
        
    with open(output_path, 'w', encoding='utf-8') as f: 
        f.write(final_srt)
        
    if log_callback: log_callback(f"Successfully saved translated file to {output_path}")
    
    # Trigger Webhook
    webhook = settings.get("jellyfin_webhook") if settings else None
    if webhook:
        try:
            import httpx
            httpx.post(webhook)
            if log_callback: log_callback("Jellyfin webhook triggered successfully.")
        except Exception as e:
            if log_callback: log_callback(f"Failed to trigger webhook: {e}")

    return True

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1: translate_single_file(sys.argv[1])
