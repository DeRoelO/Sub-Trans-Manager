import os
import re
import chardet

DUTCH_VARIANTS = {'nl', 'dut', 'dutch', 'nld', 'ned'}

def detect_encoding(file_byte: bytes) -> str:
    return chardet.detect(file_byte)['encoding']

def is_dutch_variant(filename: str) -> bool:
    filename = filename.lower()
    for variant in DUTCH_VARIANTS:
        # Check for .nl.srt, .nl.hi.srt, etc.
        if f".{variant}." in filename or filename.endswith(f".{variant}.srt"):
            return True
    return False

def detect_is_wrong_language(file_path: str, target_lang: str) -> bool:
    """Heuristic logic to detect if a file is likely NOT in the target language."""
    try:
        # We only need a sample
        with open(file_path, "rb") as f:
            bytes_data = f.read(20000) # first 20KB for better accuracy
        
        from core.translator import detect_encoding # Avoid circular import if possible, but it's already here
        encoding = detect_encoding(bytes_data) or 'utf-8'
        text = bytes_data.decode(encoding, errors='ignore').lower()
        
        # Heuristic word lists
        en_words = {' the ', ' and ', ' was ', ' that ', ' with ', ' you ', ' for ', ' have ', ' is ', ' it ', ' what ', ' are '}
        lang_maps = {
            "dutch": {' de ', ' het ', ' een ', ' en ', ' van ', ' ik ', ' is ', ' dat ', ' op ', ' te ', ' met ', ' om '},
            "french": {' le ', ' la ', ' les ', ' et ', ' un ', ' une ', ' est ', ' dans ', ' que '},
            "german": {' der ', ' die ', ' das ', ' und ', ' ein ', ' eine ', ' ist ', ' met ', ' nicht '},
            "spanish": {' el ', ' la ', ' los ', ' y ', ' en ', ' un ', ' una ', ' que ', ' con '}
        }
        
        target_words = lang_maps.get(target_lang.lower(), set())
        if not target_words: return False # Can't detect
        
        en_score = sum(1 for w in en_words if w in text)
        target_score = sum(1 for w in target_words if w in text)
        
        # If English function words are significantly more frequent than target language, it's suspicious
        # Note: 'en' is both Dutch and English, but usually 'the' vs 'de' is a better indicator.
        if en_score > target_score and en_score > 3:
            return True
    except:
        pass
    return False

def verify_language_ai(model, text_sample: str, target_language: str) -> bool:
    """Use Gemini to verify if the text is indeed in the target language."""
    prompt = (
        f"Is the following text primarily in {target_language}? "
        "Answer ONLY with 'YES' or 'NO'.\n\n"
        f"[TEXT]\n{text_sample[:1000]}"
    )
    try:
        res = model.generate_content(prompt)
        return "YES" in res.text.upper()
    except:
        return True # Default to True on failure to avoid blocking
