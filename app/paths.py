"""
Tagicus - Path Resolution

Provides the OS-standard per-user data directory (config.yml, tagicus.db)
so the app works correctly wherever it's installed, on Windows or Linux.
"""

import os
from platformdirs import user_data_dir

APP_NAME = "Tagicus"

_data_dir = None


def get_data_dir():
    global _data_dir
    if _data_dir is None:
        _data_dir = user_data_dir(APP_NAME, appauthor=False)
        os.makedirs(_data_dir, exist_ok=True)
    return _data_dir


def config_path():
    return os.path.join(get_data_dir(), "config.yml")


def db_path():
    return os.path.join(get_data_dir(), "tagicus.db")
