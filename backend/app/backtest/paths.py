"""Shared filesystem paths and logger for the backtest engine package."""
from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger("ap2web.backtest")

# NOTE: two levels up from this file == backend/app (same dir as before).
_DATA_DIR = Path(os.environ.get(
    "AP2WEB_RUNTIME_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
_DATA_DIR.mkdir(parents=True, exist_ok=True)
_HISTORY_FILE = _DATA_DIR / "backtest_history.jsonl"
_STATE_FILE = _DATA_DIR / "backtest_state.json"
_META_FILE = _DATA_DIR / "meta_learner.json"
