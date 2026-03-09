"""
scoring.py — Scoring logic for the Daily Sales Activity Tracker.

All scoring is based on: effective_count × weight_per_outcome.
Caps apply to designated low-value outcomes; everything else is uncapped.
"""

from db import get_setting


# ── Field definitions ─────────────────────────────────────────────────────────

# Maps each DB count column → (channel, outcome_name_in_weights_dict)
FIELD_MAP: dict[str, tuple[str, str]] = {
    "meeting_held":          ("Meeting",  "Meeting Held"),
    "call_dial":             ("Call",     "Dial"),
    "call_connect":          ("Call",     "Connect"),
    "call_meaningful_convo": ("Call",     "Meaningful Conversation"),
    "call_meeting_booked":   ("Call",     "Meeting Booked"),
    "email_sent":            ("Email",    "Email Sent"),
    "email_reply":           ("Email",    "Reply Received"),
    "email_positive":        ("Email",    "Positive Reply"),
    "email_meeting_booked":  ("Email",    "Meeting Booked"),
    "li_request_sent":       ("LinkedIn", "Connection Request Sent"),
    "li_accepted":           ("LinkedIn", "Connection Accepted"),
    "li_reply":              ("LinkedIn", "Reply to Message"),
    "li_meeting_booked":     ("LinkedIn", "Meeting Booked"),
}

# Human-readable label for each count field
FIELD_LABELS: dict[str, str] = {
    "meeting_held":          "Meeting Held",
    "call_dial":             "Dials",
    "call_connect":          "Connects",
    "call_meaningful_convo": "Meaningful Conversations",
    "call_meeting_booked":   "Meeting Booked",
    "email_sent":            "Emails Sent",
    "email_reply":           "Replies Received",
    "email_positive":        "Positive Replies",
    "email_meeting_booked":  "Meeting Booked",
    "li_request_sent":       "Connection Requests Sent",
    "li_accepted":           "Connections Accepted",
    "li_reply":              "Replies to Messages",
    "li_meeting_booked":     "Meeting Booked",
}

# Step name → count fields belonging to that step (steps 0-3)
STEP_FIELDS: dict[str, list[str]] = {
    "meetings": ["meeting_held"],
    "calls":    ["call_dial", "call_connect", "call_meaningful_convo",
                 "call_meeting_booked"],
    "email":    ["email_sent", "email_reply", "email_positive",
                 "email_meeting_booked"],
    "linkedin": ["li_request_sent", "li_accepted", "li_reply", "li_meeting_booked"],
}


# ── Settings accessors ────────────────────────────────────────────────────────

def get_weights() -> dict:
    return get_setting("weights", {})


def get_caps() -> dict:
    return get_setting("caps", {})


def get_channels() -> list:
    return list(get_weights().keys())


def get_outcomes(channel: str) -> list:
    return list(get_weights().get(channel, {}).keys())


def _low_value_outcomes(caps: dict) -> set:
    """Set of outcome names that are subject to daily caps."""
    return {o for ch in caps.values() for o in ch}


# ── Per-row scoring ───────────────────────────────────────────────────────────

def compute_row_score(
    row:     dict,
    weights: dict = None,
    caps:    dict = None,
) -> dict:
    """
    Full scoring breakdown for a daily_totals row (or a counts dict).

    Returns:
        fields          → per-field detail dict
        channel_totals  → {channel: total_pts}
        total           → float (total points, respecting caps)
        high_value_total→ float (points from uncapped outcomes only)
        quality_ratio   → float [0-1]
        cap_warnings    → list of human-readable cap warning strings
    """
    weights   = weights or get_weights()
    caps      = caps    or get_caps()
    low_value = _low_value_outcomes(caps)

    fields_out       = {}
    channel_totals   = {}
    total            = 0.0
    high_value_total = 0.0
    cap_warnings     = []

    for field, (channel, outcome) in FIELD_MAP.items():
        count  = int(row.get(field, 0) or 0)
        weight = float(weights.get(channel, {}).get(outcome, 0))
        cap    = caps.get(channel, {}).get(outcome)

        if cap is not None and count > cap:
            effective = cap
            cap_warnings.append(
                f"{FIELD_LABELS[field]}: {count} logged, "
                f"capped at {cap}/day — {count - cap} not counted"
            )
        else:
            effective = count

        pts = effective * weight
        total += pts
        channel_totals[channel] = channel_totals.get(channel, 0.0) + pts

        if outcome not in low_value:
            high_value_total += pts

        fields_out[field] = {
            "count":     count,
            "effective": effective,
            "weight":    weight,
            "points":    pts,
            "capped":    (cap is not None and count > cap),
        }

    qr = high_value_total / total if total > 0 else 0.0

    return {
        "fields":            fields_out,
        "channel_totals":    channel_totals,
        "total":             round(total, 1),
        "high_value_total":  round(high_value_total, 1),
        "quality_ratio":     qr,
        "cap_warnings":      cap_warnings,
    }


def compute_row_total(row: dict, weights: dict = None, caps: dict = None) -> float:
    """Quick total-only helper (avoids building the full breakdown dict)."""
    return compute_row_score(row, weights, caps)["total"]


# ── Leaderboard ───────────────────────────────────────────────────────────────

def get_leaderboard(
    rows:    list,
    reps:    list,
    weights: dict = None,
    caps:    dict = None,
) -> list:
    """
    Build a leaderboard from a list of daily_totals rows.

    Every rep in `reps` appears even when they have no data.
    Sorted by Score descending.  Top 3 get medal emoji Ranks.
    Each row: Rank, Rep, Score, <Channel> Pts, Quality Ratio, _qr (float).
    """
    weights   = weights or get_weights()
    caps      = caps    or get_caps()
    channels  = list(weights.keys())

    board: dict = {
        rep: {"total": 0.0, "hv": 0.0, **{ch: 0.0 for ch in channels}}
        for rep in reps
    }

    for r in rows:
        rep = r["rep_name"]
        if rep not in board:
            board[rep] = {"total": 0.0, "hv": 0.0, **{ch: 0.0 for ch in channels}}
        s = compute_row_score(r, weights, caps)
        board[rep]["total"] += s["total"]
        board[rep]["hv"]    += s["high_value_total"]
        for ch, pts in s["channel_totals"].items():
            if ch in board[rep]:
                board[rep][ch] += pts

    result = []
    for rep, d in board.items():
        qr = d["hv"] / d["total"] if d["total"] > 0 else 0.0
        entry = {
            "Rep":           rep,
            "Score":         round(d["total"], 1),
            "Quality Ratio": f"{qr:.0%}",
            "_qr":           qr,
        }
        for ch in channels:
            entry[f"{ch} Pts"] = round(d.get(ch, 0.0), 1)
        result.append(entry)

    result.sort(key=lambda x: x["Score"], reverse=True)
    medals = ["🥇", "🥈", "🥉"]
    for i, r in enumerate(result):
        r["Rank"] = medals[i] if i < 3 else str(i + 1)

    return result
