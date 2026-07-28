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


def long_path(path):
    """Bypass Windows' 260-char MAX_PATH limit on filesystem calls.

    Deeply nested libraries (e.g. under OneDrive) combined with long track
    titles routinely produce paths over 260 chars, which raw os/shutil/open
    calls reject even though the path is otherwise valid. The \\\\?\\ prefix
    opts into the NT kernel's much higher limit. Use this only for the actual
    filesystem call - keep the plain path for display, DB storage, and
    string operations like dirname/splitext.
    """
    if os.name != "nt":
        return path
    abspath = os.path.abspath(path)
    if abspath.startswith("\\\\?\\"):
        return abspath
    if abspath.startswith("\\\\"):
        return "\\\\?\\UNC\\" + abspath[2:]
    return "\\\\?\\" + abspath
