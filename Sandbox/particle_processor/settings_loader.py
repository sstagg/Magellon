import os
import configparser
from setup import default_setup  # Make sure path is correct relative to this file

# Optional override via environment variable
SETTINGS_PATH = os.environ.get("SETTINGS_PATH", None)

def get_settings_path():
    """Resolve the full path to settings.ini based on SETTINGS_PATH or default."""
    if SETTINGS_PATH:
        # Convert to absolute path if needed
        settings_dir = os.path.abspath(SETTINGS_PATH)
        return os.path.join(settings_dir, 'settings.ini')
    return 'settings.ini'  # default local file

def load_or_create_settings():
    """Ensure settings.ini exists; if not, create it by running default_setup()."""
    settings_file = get_settings_path()

    if not os.path.exists(settings_file):
        print(f"'settings.ini' not found at: {settings_file}")
        print("Running first-time setup...")
        default_setup(settings_file)
    else:
        print(f"Found existing 'settings.ini' at: {settings_file}")

    return settings_file
