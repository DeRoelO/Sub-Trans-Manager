import os
import json

CONFIG_DIR = os.environ.get("CONFIG_PATH", "/app/config")
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
    "auto_cleanup_suspicious": false,
    "auto_identify_untagged": true
}

# Predefined languages for the frontend to pick from
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

def ensure_config_dir():
    if not os.path.exists(CONFIG_DIR):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
        except OSError:
            pass # Use local fallback or memory if permissions fail (though Docker should map it)

def get_settings():
    ensure_config_dir()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                settings = json.load(f)
                # Merge with defaults safely
                return {**DEFAULT_SETTINGS, **settings}
        except json.JSONDecodeError:
            pass
    return DEFAULT_SETTINGS

def update_settings(new_settings: dict):
    ensure_config_dir()
    current_settings = get_settings()
    current_settings.update(new_settings)
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(current_settings, f, indent=4)
        print(f"✅ Configuration successfully saved to {CONFIG_FILE}")
        return current_settings
    except OSError as e:
        print(f"❌ CONFIG ERROR: Failed to write to {CONFIG_FILE}: {e}")
        return {"error": str(e)}

# Startup Check
print(f"📂 Config Directory: {CONFIG_DIR}")
print(f"📄 Config File: {CONFIG_FILE}")
if os.path.exists(CONFIG_DIR):
    print(f"🔓 Write Access: {os.access(CONFIG_DIR, os.W_OK)}")
else:
    print(f"🚨 Config directory does not exist yet.")

# Load API key immediately to environment if present
settings = get_settings()
if settings.get("gemini_api_key"):
    os.environ["GEMINI_API_KEY"] = settings["gemini_api_key"]
