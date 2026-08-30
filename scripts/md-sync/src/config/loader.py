from pathlib import Path
import os
import yaml


def load_config(directory: Path) -> dict:
    path = directory / "sync.yaml"
    config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for provider in config.get("providers", {}).values():
        env_name = provider.get("token_env")
        if not provider.get("token") and env_name:
            provider["token"] = os.getenv(env_name, "")
    return config
