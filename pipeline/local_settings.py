"""Private runtime settings. Never log configuration values."""
import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_local_settings():
    """Explicit path, otherwise repo-local config, then user config.

    Existing data/config.json credentials remain supported as a migration fallback.
    Malformed selected files fail closed instead of silently using another account.
    """
    explicit = os.environ.get("PAPER_LOOP_CONFIG")
    candidates = ([Path(explicit).expanduser()] if explicit else [
        REPO_ROOT / "data" / "config.local.json",
        Path.home() / ".paper-to-wechat" / "config.json",
        REPO_ROOT / "data" / "config.json",
    ])
    for path in candidates:
        if path.exists():
            try:
                settings = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(settings, dict):
                    raise ValueError()
            except (ValueError, OSError):
                raise ValueError("Invalid local configuration; expected a readable JSON object") from None
            return settings
    if explicit:
        raise FileNotFoundError("PAPER_LOOP_CONFIG does not point to an existing file")
    return {}


def setting(key, env_var=None, default=""):
    """Environment overrides local config; return a safe generic default."""
    if env_var and env_var in os.environ:
        return os.environ[env_var]
    return load_local_settings().get(key, default)
