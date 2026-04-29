import os
import json

# Try multiple locations for persistence
POSSIBLE_CONFIG_DIRS = [
    os.environ.get("CONFIG_PATH", "/app/config"),
    os.path.join(os.path.dirname(__file__), "..", "config"),
    "/tmp/srt-translator-config"
]

def get_valid_config_dir():
    for d in POSSIBLE_CONFIG_DIRS:
        try:
            if not os.path.exists(d):
                os.makedirs(d, exist_ok=True)
            # Test write access
            test_file = os.path.join(d, ".write_test")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            return d
        except:
            continue
    return "." # Fallback to current dir if all else fails

CONFIG_DIR = get_valid_config_dir()
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_SETTINGS = {
    "gemini_api_key": "",
    "ai_model": "gemini-2.0-flash",
    "target_language": "Dutch",
    "target_language_tag": "nl",
    "target_language_variants": ["nl", "dut", "dutch", "nld", "ned"],
    "films_path": "/Films",
    "series_path": "/Series",
    "batch_limit": 60,
    "batch_delay": 60,
    "cron_time": "02:00",
    "jellyfin_webhook": "",
    "auto_cleanup_suspicious": False,
    "auto_identify_untagged": True
}

SUPPORTED_LANGUAGES = [
    {"name": "Dutch", "tag": "nl", "variants": ["nl", "dut", "dutch", "nld", "ned"]},
    {"name": "English", "tag": "en", "variants": ["en", "eng", "english"]},
    {"name": "French", "tag": "fr", "variants": ["fr", "fre", "french", "fra"]},
    {"name": "German", "tag": "de", "variants": ["de", "ger", "german", "deu"]},
    {"name": "Spanish", "tag": "es", "variants": ["es", "spa", "spanish"]},
    {"name": "Italian", "tag": "it", "variants": ["it", "ita", "italian"]},
    {"name": "Portuguese", "tag": "pt", "variants": ["pt", "por", "portuguese"]},
    {"name": "Swedish", "tag": "sv", "variants": ["sv", "swe", "swedish"]},
    {"name": "Norwegian", "tag": "no", "variants": ["no", "nor", "norwegian"]},
    {"name": "Danish", "tag": "da", "variants": ["da", "dan", "danish"]},
]

def get_settings():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                settings = json.load(f)
                return {**DEFAULT_SETTINGS, **settings}
        except Exception as e:
            print(f"⚠️ Error reading config: {e}")
    return DEFAULT_SETTINGS

def update_settings(new_settings: dict):
    current_settings = get_settings()
    current_settings.update(new_settings)
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(current_settings, f, indent=4)
            f.flush()
            os.fsync(f.fileno())
        print(f"✅ Configuration saved to: {os.path.abspath(CONFIG_FILE)}")
        return current_settings
    except Exception as e:
        print(f"❌ CONFIG SAVE ERROR: {e}")
        return {"error": str(e)}

# Startup Diagnostics
print("--- CONFIGURATION DIAGNOSTICS ---")
print(f"📂 Active Config Directory: {os.path.abspath(CONFIG_DIR)}")
print(f"📄 Active Config File: {os.path.abspath(CONFIG_FILE)}")
print(f"🔓 Write Access: {os.access(CONFIG_DIR, os.W_OK)}")
print("---------------------------------")
