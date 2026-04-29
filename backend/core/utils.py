import os
import re
import chardet

# Word lists for top languages
LANG_WORDS = {
    "en": {' the ', ' and ', ' was ', ' that ', ' with ', ' you ', ' for ', ' have ', ' is ', ' it ', ' what ', ' are ', ' are '},
    "nl": {' de ', ' het ', ' een ', ' en ', ' van ', ' ik ', ' is ', ' dat ', ' op ', ' te ', ' met ', ' om ', ' niet '},
    "fr": {' le ', ' la ', ' les ', ' et ', ' un ', ' une ', ' est ', ' dans ', ' que ', ' pour ', ' pas ', ' ce '},
    "de": {' der ', ' die ', ' das ', ' und ', ' ein ', ' eine ', ' ist ', ' nicht ', ' mit ', ' sich ', ' auch '},
    "es": {' el ', ' la ', ' los ', ' y ', ' en ', ' un ', ' una ', ' que ', ' con ', ' por ', ' para ', ' si '},
    "it": {' il ', ' lo ', ' la ', ' i ', ' gli ', ' le ', ' e ', ' un ', ' una ', ' che ', ' in ', ' di '},
    "pt": {' o ', ' a ', ' os ', ' as ', ' e ', ' um ', ' uma ', ' que ', ' em ', ' para ', ' com '},
    "sv": {' och ', ' i ', ' en ', ' ett ', ' som ', ' med ', ' av ', ' för ', ' de ', ' till '},
    "no": {' og ', ' i ', ' en ', ' et ', ' som ', ' med ', ' av ', ' for ', ' det ', ' til '},
    "da": {' og ', ' i ', ' en ', ' et ', ' som ', ' med ', ' af ', ' for ', ' det ', ' til '},
    "tr": {' bir ', ' ve ', ' bu ', ' da ', ' de ', ' için ', ' çok ', ' ne ', ' o ', ' ama '},
}

def detect_encoding(file_byte: bytes) -> str:
    return chardet.detect(file_byte)['encoding']

def is_target_language_file(filename: str) -> bool:
    """Check if the filename indicates it is already in the target language."""
    from core.config import get_settings
    settings = get_settings()
    variants = settings.get("target_language_variants", ["nl", "dut", "dutch", "nld", "ned"])
    
    filename = filename.lower()
    for variant in variants:
        if f".{variant}." in filename or filename.endswith(f".{variant}.srt"):
            return True
    return False

def heuristic_detect_language(text: str) -> str:
    """Detect language based on word frequency. Fast and free."""
    text = f" {text.lower()} " # Pad for easier matching
    best_lang = "unknown"
    max_score = 0
    
    for lang, words in LANG_WORDS.items():
        score = sum(1 for w in words if w in text)
        if score > max_score:
            max_score = score
            best_lang = lang
            
    return best_lang if max_score > 2 else "unknown"

def detect_is_wrong_language(file_path: str, target_lang_name: str) -> bool:
    """Heuristic check if a file is NOT in the requested target language."""
    try:
        with open(file_path, "rb") as f: bytes_data = f.read(15000)
        encoding = detect_encoding(bytes_data) or 'utf-8'
        text = bytes_data.decode(encoding, errors='ignore')
        
        detected = heuristic_detect_language(text)
        
        # Mapping for target language name to code
        target_code = "nl" if "dutch" in target_lang_name.lower() else target_lang_name.lower()[:2]
        
        if detected != "unknown" and detected != target_code:
            # If we detected something like English for a file that should be Dutch, it's wrong.
            return True
    except:
        pass
    return False

def verify_language_ai(model, text_sample: str, target_language: str) -> bool:
    """Use Gemini to verify (expensive, but used only once per file)."""
    prompt = f"Is the following text primarily in {target_language}? Answer ONLY 'YES' or 'NO'.\n\n{text_sample[:1000]}"
    try:
        res = model.generate_content(prompt)
        return "YES" in res.text.upper()
    except:
        return True
