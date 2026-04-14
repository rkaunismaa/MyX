import yaml
from pathlib import Path


def load_config(path: str = "config.yaml") -> dict:
    with open(Path(path)) as f:
        config = yaml.safe_load(f)
    if not isinstance(config, dict):
        raise ValueError(f"Config file {path!r} is empty or not a YAML mapping")
    return config
