from __future__ import annotations

import json
from typing import Optional

from lift_tracker.profile import UserProfile
from ui.paths import HISTORY_JSON, PROFILE_JSON


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


def needs_onboarding(profile: Optional[UserProfile]) -> bool:
    if profile is None:
        return True
    return not (profile.first_name or "").strip()


def clear_profile_and_history() -> None:
    """Remove saved profile and empty workout history (for reset)."""
    try:
        PROFILE_JSON.unlink(missing_ok=True)
    except OSError:
        pass
    try:
        with open(HISTORY_JSON, "w", encoding="utf-8") as f:
            f.write("[]")
    except OSError:
        pass
