import os
import json

CONFIG_DIR = os.environ.get("CONFIG_PATH", "/SSD-DATA/mediastack/config/translator")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_SETTINGS = {
    "gemini_api_key": "",
    "films_path": "/Films",
    "series_path": "/Series",
    "batch_limit": 60,
    "batch_delay": 60,
    "cron_expression": "0 2 * * *", # Default 2 AM
    "jellyfin_webhook": ""
}

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
        return current_settings
    except OSError as e:
        return {"error": str(e)}

# Load API key immediately to environment if present
settings = get_settings()
if settings.get("gemini_api_key"):
    os.environ["GEMINI_API_KEY"] = settings["gemini_api_key"]
