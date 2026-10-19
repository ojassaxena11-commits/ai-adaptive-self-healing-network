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
        config = yaml.safe_load(f) or {}

    # Merge GNS3 environment settings
    if "gns3" not in config:
        config["gns3"] = {}
    if os.getenv("GNS3_HOST"):
        config["gns3"]["host"] = os.getenv("GNS3_HOST")
    if os.getenv("GNS3_PORT"):
        try:
            config["gns3"]["port"] = int(os.getenv("GNS3_PORT"))
        except (ValueError, TypeError):
            pass
    if os.getenv("GNS3_USER"):
        config["gns3"]["username"] = os.getenv("GNS3_USER")
    if os.getenv("GNS3_PASS") is not None:
        config["gns3"]["password"] = os.getenv("GNS3_PASS")
    if os.getenv("GNS3_PROJECT_NAME"):
        config["gns3"]["project_name"] = os.getenv("GNS3_PROJECT_NAME")

    # Override mode if set in environment (harmonizing ENV_MODE and MODE)
    env_mode = os.getenv("ENV_MODE") or os.getenv("MODE")
    if env_mode:
        normalized_mode = env_mode.strip().upper()
        config["mode"] = normalized_mode
        os.environ["ENV_MODE"] = normalized_mode
        os.environ["MODE"] = normalized_mode
    elif "mode" in config:
        normalized_mode = str(config["mode"]).strip().upper()
        config["mode"] = normalized_mode
        os.environ.setdefault("ENV_MODE", normalized_mode)
        os.environ.setdefault("MODE", normalized_mode)

    return config

# Shared configuration singleton
PROJECT_ROOT = find_project_root()
try:
    CONFIG = load_config()
except Exception:
    CONFIG = {}
