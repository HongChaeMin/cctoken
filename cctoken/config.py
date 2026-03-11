from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_DEFAULT_CONFIG_PATH = Path.home() / ".cctoken.json"


@dataclass
class Config:
    monthly_token_budget: Optional[int]
    billing_reset_day: Optional[int]  # day of month (1–28) when tokens reset


def load_config(config_path: Optional[Path] = None) -> Config:
    path = config_path or _DEFAULT_CONFIG_PATH
    if not path.exists():
        return Config(monthly_token_budget=None, billing_reset_day=None)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return Config(
            monthly_token_budget=data.get("monthly_token_budget"),
            billing_reset_day=data.get("billing_reset_day"),
        )
    except (json.JSONDecodeError, OSError):
        return Config(monthly_token_budget=None, billing_reset_day=None)


def _save(key: str, value, config_path: Optional[Path] = None) -> None:
    path = config_path or _DEFAULT_CONFIG_PATH
    existing = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    existing[key] = value
    path.write_text(json.dumps(existing, indent=2), encoding="utf-8")


def save_budget(tokens: int, config_path: Optional[Path] = None) -> None:
    _save("monthly_token_budget", tokens, config_path)


def save_reset_day(day: int, config_path: Optional[Path] = None) -> None:
    _save("billing_reset_day", day, config_path)
