import os
from pathlib import Path
from typing import Any, Dict
import yaml

def find_project_root() -> Path:
    """Traverses up from current file to locate project root containing config/config.yaml."""
    current = Path(__file__).resolve().parent
    for _ in range(5):
        if (current / "config" / "config.yaml").exists():
            return current
        current = current.parent
    # Fallback to current working directory
    return Path.cwd()

def load_dotenv(env_path: Path) -> None:
    """Minimal .env reader to avoid external dependency issues before pip completes."""
    if not env_path.exists():
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            # Strip inline comments
            if "#" in val:
                val = val.split("#", 1)[0]
            val = val.strip().strip("'\"")
            if key not in os.environ:
                os.environ[key] = val

def load_config(config_file: str = "config/config.yaml") -> Dict[str, Any]:
    """Loads YAML configuration merged with environment variables."""
    root = find_project_root()
    env_file = root / ".env"
    load_dotenv(env_file)

    cfg_path = root / config_file
    if not cfg_path.exists():
        raise FileNotFoundError(f"Configuration file not found at: {cfg_path}")

    with open(cfg_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Override mode if set in environment
    env_mode = os.getenv("ENV_MODE")
    if env_mode:
        config["mode"] = env_mode.upper()

    return config

# Shared configuration singleton
PROJECT_ROOT = find_project_root()
try:
    CONFIG = load_config()
except Exception:
    CONFIG = {}
