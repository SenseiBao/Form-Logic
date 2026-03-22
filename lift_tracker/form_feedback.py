from __future__ import annotations

from typing import Any, Dict, List


def _f(d: Dict[str, Any], key: str) -> float | None:
    v = d.get(key)
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _i(d: Dict[str, Any], key: str) -> int | None:
    v = d.get(key)
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def form_suggestions_for_set(exercise_id: str, metrics: Dict[str, Any]) -> List[str]:
    """
    Deterministic coaching lines from saved session metrics (same logic when reopening from history).
    """
    ex = (exercise_id or "").strip().lower()
    reps = _i(metrics, "total_reps")
    if reps is not None and reps <= 0:
        return [
            "No completed reps were logged in this session — stay in frame, hit your target depth, and try another set when you're ready."
        ]

    tips: List[str] = []

    if ex == "bicep_curl":
        dur = _f(metrics, "avg_rep_duration_s")
        lean = _f(metrics, "avg_max_lean_deg")
        conc = _f(metrics, "avg_conc_depth_pct")
        ecc = _f(metrics, "avg_ecc_depth_pct")

        if dur is not None and dur > 0 and dur < 1.4:
            tips.append(
                "Your average rep was quite fast — slow down and control both the curl and the lowering phase (roughly 2+ seconds per rep helps engrain form)."
            )
        if lean is not None and lean > 15.0:
            tips.append(
                "Torso movement was high — keep your chest tall and elbows fixed; avoid rocking or using momentum from your back."
            )
        if conc is not None and conc < 55.0:
            tips.append(
                "Concentric range looks shallow — curl through a fuller arc without hiking the shoulders."
            )
        if ecc is not None and ecc < 62.0:
            tips.append(
                "Resist the weight on the way down — aim for a controlled eccentric through full extension."
            )

    elif ex == "squat":
        dur = _f(metrics, "avg_rep_duration_s")
        depth = _f(metrics, "avg_depth_pct")
        lean = _f(metrics, "avg_max_lean_deg")
        pct_deep = _f(metrics, "pct_reps_deep_enough")

        if dur is not None and dur > 0 and dur < 2.0:
            tips.append(
                "Reps were on the quick side — especially on the way down, move with control so you can feel depth and balance."
            )
        if pct_deep is not None and pct_deep < 55.0:
            tips.append(
                "Several reps finished a bit shallow — try to sink until hips are closer to parallel (only as far as safe for your mobility)."
            )
        elif depth is not None and depth < 62.0:
            tips.append(
                "Average depth is on the shallow side — you should go a bit deeper while keeping heels planted and chest up."
            )
        if lean is not None and lean > 28.0:
            tips.append(
                "Forward lean was elevated — brace your core and try to stay a bit more upright through the mid-foot."
            )

    elif ex == "pullup":
        dur = _f(metrics, "avg_rep_duration_s")
        conc = _f(metrics, "avg_conc_depth_pct")
        ecc = _f(metrics, "avg_ecc_depth_pct")
        pct_hang = _f(metrics, "pct_reps_full_deadhang")
        pct_chin = _f(metrics, "pct_reps_chin_over_bar")

        if dur is not None and dur > 0 and dur < 1.5:
            tips.append(
                "Average rep speed was high — emphasize a controlled lower and a smooth pull rather than rushing."
            )
        if pct_hang is not None and pct_hang < 65.0:
            tips.append(
                "Many reps didn’t start from a full dead hang — pause with arms long at the bottom before the next pull when you can."
            )
        if pct_chin is not None and pct_chin < 60.0:
            tips.append(
                "Chin often stayed below the imaginary bar line (between the wrists) — think about lifting the chest and clearing that line each rep."
            )
        if conc is not None and conc < 48.0 and (pct_chin is None or pct_chin >= 60.0):
            tips.append(
                "Pulling range still looks a little short on average — drive a little higher toward the bar with steady shoulders."
            )
        if ecc is not None and ecc < 52.0:
            tips.append(
                "Lower yourself toward a longer hang with control before starting the next pull — avoid short, bouncy reps."
            )

    else:
        tips.append("Keep joints stacked, move smoothly, and re-record if tracking was unstable.")

    return tips
