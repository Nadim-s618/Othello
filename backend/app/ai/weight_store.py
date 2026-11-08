"""Atomic persistence for optimized AI evaluation weights."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

WEIGHTS_PATH = Path(__file__).resolve().parents[2] / "optimized_weights.json"
WEIGHTS_VERSION = 2
_LOCK = threading.Lock()


def load_weights(strategy: str, player: str) -> dict[str, float] | None:
    with _LOCK:
        data = _read()
    payload = data.get(strategy, {}).get(player)
    if not isinstance(payload, dict):
        return None
    if payload.get("_version") != WEIGHTS_VERSION:
        return None
    required = ("positional", "mobility", "corners", "pieces")
    if not all(field in payload for field in required):
        return None
    try:
        return {field: float(payload[field]) for field in required}
    except (TypeError, ValueError):
        return None


def save_weights(strategy: str, player: str, weights: Any) -> None:
    with _LOCK:
        data = _read()
        data.setdefault(strategy, {})[player] = {
            "_version": WEIGHTS_VERSION,
            "positional": float(weights.positional),
            "mobility": float(weights.mobility),
            "corners": float(weights.corners),
            "pieces": float(weights.pieces),
        }
        WEIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=WEIGHTS_PATH.parent,
            prefix="optimized_weights.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            json.dump(data, temporary, indent=2, sort_keys=True)
            temporary.write("\n")
            temporary_path = temporary.name
        os.replace(temporary_path, WEIGHTS_PATH)


def _read() -> dict[str, Any]:
    if not WEIGHTS_PATH.exists():
        return {}
    try:
        with WEIGHTS_PATH.open("r", encoding="utf-8") as weights_file:
            data = json.load(weights_file)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return {}
