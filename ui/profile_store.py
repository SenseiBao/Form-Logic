from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from lift_tracker.profile import UserProfile
from ui.paths import HISTORY_JSON, PROFILE_JSON, WEIGHT_LOG_JSON


def load_profile() -> Optional[UserProfile]:
    if not PROFILE_JSON.exists():
        return None
    try:
        with open(PROFILE_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return None
        return UserProfile.from_dict(data)
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return None


def save_profile(profile: UserProfile) -> None:
    try:
        with open(PROFILE_JSON, "w", encoding="utf-8") as f:
            json.dump(profile.to_dict(), f, indent=2)
    except OSError:
        pass


def load_weight_log() -> List[Dict[str, Any]]:
    if not WEIGHT_LOG_JSON.exists():
        return []
    try:
        with open(WEIGHT_LOG_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def log_weight(weight_kg: float, *, timestamp: Optional[str] = None) -> None:
    entries = load_weight_log()
    entries.append({
        "timestamp": timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "weight_kg": weight_kg,
    })
    try:
        with open(WEIGHT_LOG_JSON, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2)
    except OSError:
        pass


def delete_weight_entry(index: int) -> None:
    entries = load_weight_log()
    if 0 <= index < len(entries):
        entries.pop(index)
        try:
            with open(WEIGHT_LOG_JSON, "w", encoding="utf-8") as f:
                json.dump(entries, f, indent=2)
        except OSError:
            pass


def needs_onboarding(profile: Optional[UserProfile]) -> bool:
    if profile is None:
        return True
    return not (profile.first_name or "").strip()


def clear_profile_and_history() -> None:
    """Remove saved profile, weight log, and empty workout history (for reset)."""
    for path in (PROFILE_JSON, WEIGHT_LOG_JSON):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
    try:
        with open(HISTORY_JSON, "w", encoding="utf-8") as f:
            f.write("[]")
    except OSError:
        pass
