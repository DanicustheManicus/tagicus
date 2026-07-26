import os, yaml
import paths

CONFIG_PATH = paths.config_path()

DEFAULT_CONFIG = """# Tagicus Configuration
# ======================

api_keys:
  acoustid: YOUR_ACOUSTID_KEY
  discogs: YOUR_DISCOGS_TOKEN
"""


def load_config():
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w") as f:
            f.write(DEFAULT_CONFIG)
        return {}
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f) or {}

def get_key(config, service):
    keys = config.get("api_keys", {})
    key = keys.get(service)
    if not key or key.startswith("YOUR_"):
        return None
    return key
