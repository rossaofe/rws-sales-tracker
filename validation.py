"""
validation.py — Funnel constraint validation for the Daily Sales Activity Tracker.

Each channel's outcomes must follow a funnel order:
  earlier-stage count >= later-stage count

Chains (by step name):
  calls:    dial >= connect >= meaningful_convo >= qualified >= meeting_booked
  email:    sent >= reply >= positive >= meeting_booked
  linkedin: request_sent >= accepted >= reply >= convo_started >= meeting_booked
  meetings: no constraint
"""

from scoring import FIELD_LABELS


# ── Funnel chains ─────────────────────────────────────────────────────────────
# Each chain is an ordered list of DB field names; every element must be
# <= the element before it.

FUNNEL_CHAINS: dict[str, list[str]] = {
    "calls": [
        "call_dial",
        "call_connect",
        "call_meaningful_convo",
        "call_meeting_booked",
    ],
    "email": [
        "email_sent",
        "email_reply",
        "email_positive",
        "email_meeting_booked",
    ],
    "linkedin": [
        "li_request_sent",
        "li_accepted",
        "li_reply",
        "li_convo_started",
        "li_meeting_booked",
    ],
    "meetings": [],  # no funnel constraint
}


# ── Validation ────────────────────────────────────────────────────────────────

def validate_step(step_name: str, counts: dict) -> list[str]:
    """
    Validate funnel order for a single step.

    Returns a list of human-readable error strings (empty list = valid).
    Each error identifies the two fields and their current values.
    """
    chain = FUNNEL_CHAINS.get(step_name, [])
    errors: list[str] = []
    for i in range(len(chain) - 1):
        a, b = chain[i], chain[i + 1]
        va = int(counts.get(a, 0) or 0)
        vb = int(counts.get(b, 0) or 0)
        if vb > va:
            errors.append(
                f"{FIELD_LABELS[b]} ({vb}) cannot exceed {FIELD_LABELS[a]} ({va})"
            )
    return errors


def validate_all(counts: dict) -> dict[str, list[str]]:
    """
    Validate funnel order for all steps.

    Returns {step_name: [error_str, ...]}; steps with no errors map to [].
    """
    return {step: validate_step(step, counts) for step in FUNNEL_CHAINS}


def has_errors(validation_result: dict) -> bool:
    """Return True if any step in a validate_all() result has violations."""
    return any(errs for errs in validation_result.values())


# ── Auto-fix ──────────────────────────────────────────────────────────────────

def autofix_step(step_name: str, counts: dict) -> dict:
    """
    Return a copy of counts with later-stage values clamped to their preceding stage.

    Fixes are applied left-to-right so cascades are handled correctly:
      dial=7, connect=10, meaningful=9  →  connect=7, meaningful=7
    """
    chain = FUNNEL_CHAINS.get(step_name, [])
    result = {k: int(v or 0) for k, v in counts.items()}
    for i in range(len(chain) - 1):
        a, b = chain[i], chain[i + 1]
        if result.get(b, 0) > result.get(a, 0):
            result[b] = result.get(a, 0)
    return result


def autofix_all(counts: dict) -> dict:
    """Apply autofix to every step and return a fully corrected counts dict."""
    result = {k: int(v or 0) for k, v in counts.items()}
    for step in FUNNEL_CHAINS:
        result.update(autofix_step(step, result))
    return result
