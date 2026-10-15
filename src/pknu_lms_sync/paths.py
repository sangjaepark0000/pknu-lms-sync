import os
from pathlib import Path


def _xdg(name: str, fallback: str) -> Path:
    return Path(os.environ.get(name, Path.home() / fallback)).expanduser()


CONFIG_DIR = _xdg("XDG_CONFIG_HOME", ".config") / "pknu-lms-sync"
STATE_DIR = _xdg("XDG_STATE_HOME", ".local/state") / "pknu-lms-sync"
CONFIG_PATH = CONFIG_DIR / "config.json"
DEFAULT_ROOT = Path.home() / "Documents" / "PKNU"


def ensure_private_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)
