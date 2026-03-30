"""
app.py — Weighted Sales Activity Tracker  ·  UI v2
Sidebar global controls  |  Wizard stepper  |  Live score panel  |  Dashboard  |  Import  |  Settings
"""

import io
import json
import os
import re
from datetime import date, datetime, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from db import (
    COUNT_FIELDS,
    add_proofs,
    delete_daily_total,
    delete_rep_totals,
    get_daily_totals,
    get_existing_row,
    get_setting,
    init_db,
    set_setting,
    upsert_daily_total,
)
from scoring import (
    FIELD_LABELS,
    FIELD_MAP,
    STEP_FIELDS,
    compute_row_score,
    compute_row_total,
    get_channels,
    get_leaderboard,
    get_weights,
)
from validation import (
    autofix_all,
    autofix_step,
    has_errors,
    validate_all,
    validate_step,
)

# ══════════════════════════════════════════════════════════════════════════════
# Bootstrap
# ══════════════════════════════════════════════════════════════════════════════

init_db()
_DATA_DIR   = os.environ.get("DATA_DIR", ".")
_UPLOAD_DIR = os.path.join(_DATA_DIR, "uploads")
os.makedirs(_UPLOAD_DIR, exist_ok=True)

st.set_page_config(
    page_title="RWS Sales Tracker",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ══════════════════════════════════════════════════════════════════════════════
# Constants
# ══════════════════════════════════════════════════════════════════════════════

WIZARD_STEPS = ["Meetings", "Calls", "Email", "LinkedIn", "Review & Save"]
STEP_NAMES   = ["meetings", "calls", "email", "linkedin"]
STEP_ICONS   = ["📅", "📞", "✉️", "🔗", "✅"]

CHANNEL_ICONS = {"Call": "📞", "Email": "✉️", "LinkedIn": "🔗", "Meeting": "📅"}

OUTCOME_HELP = {
    "meeting_held":          "A scheduled meeting you attended or ran today.",
    "call_dial":             "Any outbound call attempt — includes no-answers, voicemails, and hang-ups.",
    "call_connect":          "Call where the prospect answered and you spoke, even briefly.",
    "call_meaningful_convo": "Conversation where useful discovery info was gathered or relationship advanced.",
    "call_meeting_booked":   "A meeting scheduled as a direct result of this call.",
    "email_sent":            "Any new outbound prospecting email sent today (not replies).",
    "email_reply":           "Any reply received to your outbound emails, positive or negative.",
    "email_positive":        "Reply showing genuine interest or requesting information / a meeting.",
    "email_meeting_booked":  "A meeting confirmed directly from an email thread today.",
    "li_request_sent":       "New LinkedIn connection request sent to a prospect today.",
    "li_accepted":           "A prospect accepted your LinkedIn connection request.",
    "li_reply":              "Any reply received to a LinkedIn message you sent.",
    "li_meeting_booked":     "A meeting booked as a direct result of your LinkedIn outreach.",
}

CHART_COLORS = px.colors.qualitative.Set2
BRAND_RED    = "#B91C1C"
BRAND_GREEN  = "#10B981"
BRAND_AMBER  = "#F59E0B"


# ══════════════════════════════════════════════════════════════════════════════
# SVG icon helper  (Heroicons outline — MIT licence)
# ══════════════════════════════════════════════════════════════════════════════

def _svg(name: str, size: int = 16, color: str = "currentColor") -> str:
    _P = {
        "phone":    "M2.25 6.338c0-1.379 1.244-2.336 2.595-2.057l5.138 1.028a2.25 2.25 0 011.437 3.234l-.463.927a13.582 13.582 0 006.564 6.564l.927-.463a2.25 2.25 0 013.234 1.437l1.028 5.138c.28 1.351-.678 2.595-2.057 2.595H19.5A17.25 17.25 0 012.25 4.5v-.162z",
        "envelope": "M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75",
        "link":     "M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m13.35-.622l1.757-1.757a4.5 4.5 0 00-6.364-6.364l-4.5 4.5a4.5 4.5 0 001.242 7.244",
        "calendar": "M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5",
        "check":    "M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z",
        "info":     "M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z",
        "lightning":"M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z",
        "star":     "M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.563.563 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z",
        "chart":    "M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z",
        "trending": "M2.25 18L9 11.25l4.306 4.307a11.95 11.95 0 015.814-5.519l2.74-1.22m0 0l-5.94-2.28m5.94 2.28l-2.28 5.941",
        "user":     "M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z",
        "target":   "M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z",
        "book":     "M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25",
    }
    path = _P.get(name, "")
    if not path:
        return ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.75" '
        f'stroke-linecap="round" stroke-linejoin="round" '
        f'style="display:inline-block;vertical-align:middle;flex-shrink:0">'
        f'<path d="{path}"/></svg>'
    )


# Channel icon map (SVG) — used in HTML-rendered sections
_CH_SVG = {
    "Call":    lambda s=15: _svg("phone",    s, "#94A3B8"),
    "Email":   lambda s=15: _svg("envelope", s, "#94A3B8"),
    "LinkedIn":lambda s=15: _svg("link",     s, "#94A3B8"),
    "Meeting": lambda s=15: _svg("calendar", s, "#94A3B8"),
}


# ══════════════════════════════════════════════════════════════════════════════
# Per-rep target helpers
# ══════════════════════════════════════════════════════════════════════════════

def _get_rep_targets(rep: str) -> dict:
    """Return targets for a specific rep. Handles old shared format transparently."""
    all_tgt = get_setting("targets", {})
    if not all_tgt:
        return {}
    first = next(iter(all_tgt.values()), None)
    if isinstance(first, dict):
        return all_tgt.get(rep, {})
    # Old format — shared across all reps; return as-is for backwards compat
    return all_tgt


def _set_rep_targets(rep: str, targets: dict) -> None:
    """Save targets for a specific rep, migrating old shared format if needed."""
    all_tgt = get_setting("targets", {})
    if all_tgt:
        first = next(iter(all_tgt.values()), None)
        if first is not None and not isinstance(first, dict):
            all_tgt = {}   # discard old shared format, start per-rep
    all_tgt[rep] = targets
    set_setting("targets", all_tgt)


# ══════════════════════════════════════════════════════════════════════════════
# Score reasoning
# ══════════════════════════════════════════════════════════════════════════════

def _score_reasoning(counts: dict, scored: dict) -> list:
    """Return a list of insight strings explaining the current score."""
    total = scored["total"]
    ch    = scored["channel_totals"]
    qr    = scored["quality_ratio"]

    if total == 0:
        return ["Enter your activity numbers to see personalised score insights."]

    lines = []

    # Top channel
    ranked = sorted([(c, p) for c, p in ch.items() if p > 0], key=lambda x: x[1], reverse=True)
    if ranked:
        top_ch, top_pts = ranked[0]
        lines.append(f"**{top_ch}** is your strongest channel — {top_pts:.0f} pts ({top_pts/total*100:.0f}% of total).")

    # Calls
    dial    = counts.get("call_dial", 0)
    connect = counts.get("call_connect", 0)
    convo   = counts.get("call_meaningful_convo", 0)
    if dial > 0 and connect > 0:
        cr    = connect / dial * 100
        label = "strong" if cr >= 25 else "average" if cr >= 15 else "low"
        lines.append(f"Call connect rate **{cr:.0f}%** ({connect}/{dial} dials) — {label} for cold outreach.")
    if convo > 0 and connect > 0:
        mc = convo / connect * 100
        lines.append(f"**{convo}** meaningful conversation{'s' if convo != 1 else ''} from {connect} connects ({mc:.0f}%) — high-multiplier call outcomes.")

    # Email
    sent  = counts.get("email_sent", 0)
    reply = counts.get("email_reply", 0)
    if sent > 0 and reply > 0:
        rr = reply / sent * 100
        lines.append(f"Email reply rate **{rr:.0f}%** ({reply}/{sent}) — {'above' if rr >= 5 else 'below'} the typical 5% benchmark.")

    # Meetings booked
    booked = (counts.get("call_meeting_booked", 0)
              + counts.get("email_meeting_booked", 0)
              + counts.get("li_meeting_booked", 0))
    if booked > 0:
        lines.append(f"**{booked} meeting{'s' if booked != 1 else ''} booked** across all channels — the highest-value outcomes in the model.")

    # Quality ratio
    if qr >= 0.7:
        lines.append(f"Quality ratio **{qr:.0%}** — excellent. High-value outcomes dominate your week.")
    elif qr >= 0.5:
        lines.append(f"Quality ratio **{qr:.0%}** — solid balance of volume and quality.")
    elif qr >= 0.3:
        lines.append(f"Quality ratio **{qr:.0%}** — moderate. More meaningful conversations would lift this significantly.")
    else:
        lines.append(f"Quality ratio **{qr:.0%}** — volume-heavy. Focus on conversations and booked meetings for the biggest score gains.")

    return lines


# ══════════════════════════════════════════════════════════════════════════════
# CSS
# ══════════════════════════════════════════════════════════════════════════════

_CSS = """
<style>

/* ── Base typography ────────────────────────────────────────────────────── */
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
}

/* ── Hide default Streamlit chrome ─────────────────────────────────────── */
#MainMenu, footer { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent; }

/* ── Sidebar ────────────────────────────────────────────────────────────── */
section[data-testid="stSidebar"] {
    border-right: 1px solid rgba(255,255,255,0.07) !important;
}
section[data-testid="stSidebar"] > div:first-child { padding-top: 0.5rem; }

.sb-logo {
    display: flex; align-items: center; gap: 10px;
    padding: 12px 0 16px 0;
    border-bottom: 1px solid rgba(255,255,255,0.07);
    margin-bottom: 16px;
}
.sb-logo-icon { font-size: 1.7rem; line-height: 1; }
.sb-logo-name { font-size: 0.95rem; font-weight: 700; line-height: 1.25; }
.sb-logo-sub  { font-size: 0.7rem; color: #94A3B8; margin-top: 1px; }
.sb-logo-badge {
    display: inline-block; background: #B91C1C; color: #fff;
    font-size: 0.6rem; font-weight: 800; letter-spacing: 0.06em;
    padding: 1px 6px; border-radius: 4px; margin-top: 3px;
    text-transform: uppercase;
}

.sb-section {
    font-size: 0.65rem; font-weight: 700; letter-spacing: 0.09em;
    text-transform: uppercase; color: #64748B;
    padding: 14px 0 6px 0;
}
.sb-draft-score {
    font-size: 1.5rem; font-weight: 800; color: #DC2626;
    letter-spacing: -0.03em; line-height: 1;
}
.sb-draft-label {
    font-size: 0.7rem; color: #94A3B8; font-weight: 500; margin-bottom: 8px;
}

/* ── Tabs ───────────────────────────────────────────────────────────────── */
button[data-baseweb="tab"] {
    font-size: 0.87rem !important; font-weight: 500 !important;
    padding: 10px 16px !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
    font-weight: 700 !important;
}

/* ── Cards — bordered containers ───────────────────────────────────────── */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 14px !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    box-shadow: 0 2px 10px rgba(0,0,0,0.3), 0 1px 3px rgba(0,0,0,0.2) !important;
}
div[data-testid="stVerticalBlockBorderWrapper"] > div {
    padding: 8px 12px !important;
}

/* ── Card header helper ─────────────────────────────────────────────────── */
.card-hdr {
    display: flex; align-items: center; gap: 10px;
    padding-bottom: 12px; margin-bottom: 14px;
    border-bottom: 1px solid rgba(255,255,255,0.07);
}
.card-hdr-icon  { font-size: 1.35rem; line-height: 1; }
.card-hdr-title { font-size: 1.0rem; font-weight: 700; line-height: 1.2; }
.card-hdr-sub   { font-size: 0.75rem; color: #94A3B8; margin-top: 2px; }

/* ── Section label ──────────────────────────────────────────────────────── */
.sec-label {
    font-size: 0.65rem; font-weight: 700; letter-spacing: 0.09em;
    text-transform: uppercase; color: #64748B;
    padding-bottom: 8px; margin: 18px 0 8px 0;
    border-bottom: 1px solid rgba(255,255,255,0.06);
}

/* ── HTML Stepper ───────────────────────────────────────────────────────── */
.wiz-stepper {
    display: flex; align-items: flex-start;
    padding: 16px 0 4px 0; width: 100%; overflow: visible;
}
.wiz-step { display: flex; flex-direction: column; align-items: center; flex: 0 0 auto; }
.wiz-circle {
    width: 36px; height: 36px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-weight: 700; font-size: 0.82rem;
    border: 2px solid transparent; transition: all 0.2s;
}
.wiz-step.done    .wiz-circle { background:#10B981; color:#fff; border-color:#10B981; }
.wiz-step.active  .wiz-circle { background:#B91C1C; color:#fff; border-color:#B91C1C;
                                  box-shadow: 0 0 0 4px rgba(185,28,28,0.28); }
.wiz-step.pending .wiz-circle { background:rgba(255,255,255,0.06); color:#64748B;
                                  border-color:rgba(255,255,255,0.12); }
.wiz-label { margin-top:6px; font-size:0.67rem; font-weight:600; text-align:center;
              white-space:nowrap; letter-spacing:0.02em; max-width:82px; line-height:1.3; }
.wiz-step.done    .wiz-label { color:#10B981; }
.wiz-step.active  .wiz-label { color:#DC2626; }
.wiz-step.pending .wiz-label { color:#64748B; }
.wiz-line  { flex:1; height:2px; margin-top:17px; min-width:16px; border-radius:1px; }
.wiz-line.done    { background:#B91C1C; }
.wiz-line.pending { background:rgba(255,255,255,0.10); }

/* ── Stepper jump buttons (icon-only pill row) ─────────────────────────── */
.step-jump-row button[data-testid="baseButton-secondary"],
.step-jump-row button[data-testid="baseButton-primary"] {
    min-height: 30px !important;
    padding: 3px 4px !important;
    font-size: 1.05rem !important;
    border-radius: 20px !important;
    line-height: 1 !important;
}

/* ── All buttons global polish ──────────────────────────────────────────── */
button[data-testid="baseButton-primary"] {
    border-radius: 9px !important; font-weight: 600 !important;
    letter-spacing: 0.01em !important; transition: all 0.15s ease !important;
}
button[data-testid="baseButton-secondary"] {
    border-radius: 9px !important; font-weight: 500 !important;
    border-color: rgba(255,255,255,0.12) !important;
}

/* ── Number inputs ──────────────────────────────────────────────────────── */
div[data-testid="stNumberInput"] input {
    border-radius: 8px !important; font-weight: 700 !important;
    font-size: 1.15rem !important; text-align: center !important;
}

/* ── KPI metric cards ───────────────────────────────────────────────────── */
div[data-testid="stMetric"] {
    border-radius: 12px; border: 1px solid rgba(255,255,255,0.08);
    padding: 14px 16px 10px 16px; background: rgba(185,28,28,0.06);
}
div[data-testid="stMetric"] label {
    font-size: 0.68rem !important; font-weight: 700 !important;
    text-transform: uppercase !important; letter-spacing: 0.07em !important;
    color: #94A3B8 !important;
}
div[data-testid="stMetric"] [data-testid="stMetricValue"] {
    font-size: 1.85rem !important; font-weight: 800 !important;
    letter-spacing: -0.025em !important; color: #DC2626 !important;
}

/* ── Live score panel ───────────────────────────────────────────────────── */
.lsp-total      { font-size:2.6rem; font-weight:900; color:#DC2626; letter-spacing:-0.04em; line-height:1; }
.lsp-total-sub  { font-size:0.68rem; font-weight:700; text-transform:uppercase;
                   letter-spacing:0.07em; color:#94A3B8; margin-bottom:4px; }
.lsp-qr-badge   { display:inline-block; background:rgba(16,185,129,0.12); color:#10B981;
                   border-radius:6px; font-size:0.8rem; font-weight:700; padding:2px 10px;
                   margin:8px 0 14px 0; }
.lsp-prog-track { height:6px; border-radius:3px; background:rgba(255,255,255,0.10);
                   margin:4px 0 14px 0; overflow:hidden; }
.lsp-prog-fill  { height:100%; border-radius:3px;
                   background:linear-gradient(90deg,#B91C1C 0%,#10B981 100%);
                   transition:width .35s ease; }
.lsp-sec        { font-size:0.63rem; font-weight:700; text-transform:uppercase;
                   letter-spacing:0.09em; color:#64748B; margin:12px 0 5px 0; }
.lsp-ch-row     { display:flex; justify-content:space-between; align-items:center;
                   padding:5px 0; border-bottom:1px solid rgba(255,255,255,0.07);
                   font-size:0.82rem; }
.lsp-ch-row:last-child { border-bottom:none; }
.lsp-ch-name    { color:#94A3B8; }
.lsp-ch-pts     { font-weight:700; color:#DC2626; }
.lsp-cap-warn   { font-size:0.74rem; padding:5px 9px; border-radius:7px;
                   background:rgba(245,158,11,0.10); color:#F59E0B;
                   margin-top:5px; border:1px solid rgba(245,158,11,0.22); line-height:1.4; }
.lsp-step-icons { display:flex; gap:6px; margin-top:4px; font-size:1.15rem; }

/* ── Leaderboard table ──────────────────────────────────────────────────── */
.lb-wrap { border-radius:12px; overflow:hidden; border:1px solid rgba(255,255,255,0.08); }
.lb-table { width:100%; border-collapse:collapse; font-size:0.83rem; }
.lb-table thead tr { border-bottom:2px solid rgba(255,255,255,0.08); }
.lb-table th {
    padding:9px 13px; text-align:left; font-size:0.65rem;
    font-weight:700; text-transform:uppercase; letter-spacing:0.08em; color:#64748B;
}
.lb-table td { padding:11px 13px; border-bottom:1px solid rgba(255,255,255,0.05); }
.lb-table tr:last-child td { border-bottom:none; }
.lb-table tr.lb-sel td { background:rgba(185,28,28,0.08); }
.lb-table tr.lb-sel td:first-child { border-left:3px solid #B91C1C; padding-left:10px; }
.lb-rank    { font-size:1.1em; }
.lb-score   { font-weight:800; color:#DC2626; }
.lb-qr      { color:#10B981; font-weight:600; }
.lb-rep     { font-weight:600; }

/* ── Review breakdown ───────────────────────────────────────────────────── */
.rev-ch-hdr {
    display:flex; justify-content:space-between; align-items:center;
    padding:8px 0; margin:10px 0 4px 0;
    border-bottom:2px solid rgba(255,255,255,0.08); font-weight:700; font-size:0.9rem;
}
.rev-ch-pts { color:#DC2626; }
.rev-table  { width:100%; border-collapse:collapse; font-size:0.82rem; margin-bottom:12px; }
.rev-table td { padding:7px 0; border-bottom:1px solid rgba(255,255,255,0.06); }
.rev-table tr:last-child td { border-bottom:none; }
.rev-pts    { font-weight:700; text-align:right; color:#DC2626; }
.rev-capped { font-size:0.72rem; color:#F59E0B; }

/* ── Import / settings form cards ──────────────────────────────────────── */
.import-info {
    padding:12px 16px; border-radius:10px;
    border:1px solid rgba(255,255,255,0.08); background:rgba(185,28,28,0.04);
    font-size:0.84rem; line-height:1.6; margin-bottom:16px;
}

/* ── Funnel validation errors ───────────────────────────────────────────── */
.funnel-err-box {
    border-radius: 10px;
    border: 1px solid rgba(239,68,68,0.35);
    background: rgba(239,68,68,0.08);
    padding: 10px 14px 8px 14px;
    margin: 12px 0 6px 0;
}
.funnel-err-title {
    font-size: 0.75rem; font-weight: 700; color: #EF4444;
    text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 6px;
}
.funnel-err-item {
    font-size: 0.79rem; color: #FCA5A5;
    padding: 2px 0 2px 4px; line-height: 1.5;
}

/* ── App hero header ───────────────────────────────────────────────────── */
.app-hero {
    padding: 18px 0 14px 0;
    margin-bottom: 6px;
    border-bottom: 1px solid rgba(255,255,255,0.06);
}
.app-hero-eyebrow {
    font-size: 0.62rem; font-weight: 700; letter-spacing: 0.14em;
    text-transform: uppercase; color: #B91C1C; margin-bottom: 5px;
}
.app-hero-title {
    font-size: 1.75rem; font-weight: 900; letter-spacing: -0.035em;
    line-height: 1.1; color: #F8FAFC; margin-bottom: 5px;
}
.app-hero-meta { font-size: 0.82rem; color: #64748B; }
.app-hero-meta strong { color: #94A3B8; font-weight: 600; }

/* ── Step counter ───────────────────────────────────────────────────────── */
.step-counter {
    font-size: 0.68rem; font-weight: 600; color: #64748B;
    text-transform: uppercase; letter-spacing: 0.09em;
    text-align: right; padding-top: 6px;
}
.step-counter-accent { color: #B91C1C; font-weight: 800; }

/* ── Section title ──────────────────────────────────────────────────────── */
.section-title {
    font-size: 1.2rem; font-weight: 800; letter-spacing: -0.02em;
    color: #F8FAFC; margin-bottom: 2px; margin-top: 8px;
}
.section-title-sub { font-size: 0.78rem; color: #64748B; margin-bottom: 14px; }

/* ── Channel mini-bar (live score panel) ────────────────────────────────── */
.ch-bar-wrap {
    display: flex; align-items: center; gap: 8px; padding: 5px 0;
    border-bottom: 1px solid rgba(255,255,255,0.05);
}
.ch-bar-wrap:last-child { border-bottom: none; }
.ch-bar-label { font-size: 0.74rem; color: #94A3B8; width: 68px; flex-shrink: 0; }
.ch-bar-track {
    flex: 1; height: 5px; border-radius: 3px;
    background: rgba(255,255,255,0.07); overflow: hidden;
}
.ch-bar-fill  { height: 100%; border-radius: 3px; background: #B91C1C; transition: width .4s ease; }
.ch-bar-pts   { font-size: 0.74rem; font-weight: 700; color: #DC2626; width: 30px; text-align: right; flex-shrink: 0; }

/* ── Review receipt header ──────────────────────────────────────────────── */
.receipt-header {
    display: flex; justify-content: space-between; align-items: flex-end;
    padding: 4px 0 16px 0;
    border-bottom: 1px solid rgba(255,255,255,0.07);
    margin-bottom: 18px;
}
.receipt-title  { font-size: 1.15rem; font-weight: 800; letter-spacing: -0.02em; color: #F8FAFC; }
.receipt-meta   { font-size: 0.78rem; color: #64748B; margin-top: 4px; }
.receipt-score  { font-size: 2.4rem; font-weight: 900; color: #DC2626; letter-spacing: -0.05em; line-height: 1; }
.receipt-score-lbl { font-size: 0.62rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.09em; color: #64748B; margin-bottom: 2px; }
.receipt-qr     { font-size: 0.78rem; font-weight: 600; margin-top: 3px; }

/* ── Leaderboard top-3 row tints ────────────────────────────────────────── */
.lb-table tr.lb-gold   td { background: rgba(251,191,36,0.05); }
.lb-table tr.lb-silver td { background: rgba(148,163,184,0.04); }
.lb-table tr.lb-bronze td { background: rgba(180,100,40,0.05); }

/* ── Dashboard chart headings ───────────────────────────────────────────── */
.chart-title { font-size: 0.88rem; font-weight: 700; color: #E2E8F0; margin-bottom: 2px; }
.chart-sub   { font-size: 0.72rem; color: #64748B; margin-bottom: 8px; }

/* ── Wider primary buttons ──────────────────────────────────────────────── */
button[data-testid="baseButton-primary"] {
    padding: 0.55rem 1.2rem !important;
    font-size: 0.88rem !important;
}

</style>
"""

st.markdown(_CSS, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# Session-state helpers
# ══════════════════════════════════════════════════════════════════════════════

def _init_session() -> None:
    if "wizard_step" not in st.session_state:
        st.session_state.wizard_step = 0
    if "_draft" not in st.session_state:
        st.session_state["_draft"] = {f: 0 for f in COUNT_FIELDS}
    # Restore widget keys from _draft so each step's form shows the saved values
    for f in COUNT_FIELDS:
        if f not in st.session_state:
            st.session_state[f] = st.session_state["_draft"].get(f, 0)
    if "draft_proofs" not in st.session_state:
        st.session_state.draft_proofs = {s: [] for s in STEP_NAMES}
    if "proof_keys" not in st.session_state:
        st.session_state.proof_keys = {s: set() for s in STEP_NAMES}
    if "_loaded_for" not in st.session_state:
        st.session_state["_loaded_for"] = None
    if "_step_errors" not in st.session_state:
        st.session_state["_step_errors"] = []
    if "_error_step" not in st.session_state:
        st.session_state["_error_step"] = ""


def _clear_draft() -> None:
    st.session_state["_draft"] = {f: 0 for f in COUNT_FIELDS}
    st.session_state.wizard_step = 0
    for f in COUNT_FIELDS:
        if f in st.session_state:
            del st.session_state[f]
    st.session_state.draft_proofs = {s: [] for s in STEP_NAMES}
    st.session_state.proof_keys   = {s: set() for s in STEP_NAMES}
    if "draft_notes" in st.session_state:
        del st.session_state["draft_notes"]
    st.session_state["_loaded_for"] = None
    st.rerun()


_init_session()


def _auto_load_existing() -> None:
    """
    When rep or date changes, pull that week's saved record into the count
    fields. Date is snapped to week-start before lookup.
    If no record exists the fields are left as-is (initialised to 0
    by _init_session on first load; only Clear Draft resets them).
    """
    rep      = st.session_state.get("draft_rep", "")
    dval_raw = st.session_state.get("draft_date", date.today())
    if isinstance(dval_raw, str):
        dval_raw = date.fromisoformat(dval_raw)
    dval = str(week_start(dval_raw))
    key  = (rep, dval)
    if st.session_state.get("_loaded_for") == key:
        return  # already loaded for this rep + date
    if rep:
        row = get_existing_row(dval, rep)
        if row:
            for f in COUNT_FIELDS:
                val = row.get(f, 0)
                st.session_state[f] = val
                st.session_state["_draft"][f] = val
    st.session_state["_loaded_for"] = key


# ══════════════════════════════════════════════════════════════════════════════
# Utility helpers
# ══════════════════════════════════════════════════════════════════════════════

def week_start(ref: date = None) -> date:
    ref = ref or date.today()
    offset = ref.weekday() if get_setting("week_starts_monday", True) else (ref.weekday() + 1) % 7
    return ref - timedelta(days=offset)


def month_start(ref: date = None) -> date:
    return (ref or date.today()).replace(day=1)


def sum_scores(rows: list, weights: dict = None, caps: dict = None) -> float:
    w = weights or get_weights()
    c = caps    or {}
    return round(sum(compute_row_total(r, w, c) for r in rows), 1)


def create_summary_csv(rows: list, reps: list) -> str:
    if not rows:
        return ""
    w, c = get_weights(), {}
    buf  = io.StringIO()

    buf.write("LEADERBOARD\n")
    lb = pd.DataFrame(get_leaderboard(rows, reps, w, c)).drop(columns=["_qr"], errors="ignore")
    lb.to_csv(buf, index=False)

    buf.write("\nWEEKLY TOTALS WITH SCORE\n")
    scored_rows = []
    for r in rows:
        s = compute_row_score(r, w, c)
        scored_rows.append({
            "Date": r["date"], "Rep": r["rep_name"],
            "Score": s["total"], "Quality Ratio": f"{s['quality_ratio']:.0%}",
            **{FIELD_LABELS[f]: r.get(f, 0) for f in COUNT_FIELDS},
        })
    pd.DataFrame(scored_rows).to_csv(buf, index=False)
    return buf.getvalue()


def _apply_chart_style(fig, height: int = 290):
    fig.update_layout(
        template="plotly_dark",
        height=height,
        margin=dict(l=0, r=0, t=22, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, system-ui, sans-serif", size=11, color="#94A3B8"),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
            font=dict(size=11), bgcolor="rgba(0,0,0,0)",
        ),
    )
    fig.update_xaxes(
        showgrid=False, showline=False,
        tickfont=dict(size=10, color="#64748B"),
        zeroline=False,
    )
    fig.update_yaxes(
        gridcolor="rgba(255,255,255,0.06)", showline=False,
        tickfont=dict(size=10, color="#64748B"),
        zeroline=False,
    )
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# Draft actions (sidebar buttons)
# ══════════════════════════════════════════════════════════════════════════════

def _zero_all() -> None:
    st.session_state["_draft"] = {f: 0 for f in COUNT_FIELDS}
    for f in COUNT_FIELDS:
        if f in st.session_state:
            del st.session_state[f]


def _copy_last_week() -> bool:
    rep = st.session_state.get("draft_rep", "")
    if not rep:
        return False
    last_wk = str(week_start(date.today() - timedelta(days=7)))
    row = get_existing_row(last_wk, rep)
    if not row:
        return False
    for f in COUNT_FIELDS:
        val = row.get(f, 0)
        st.session_state[f] = val
        st.session_state["_draft"][f] = val
    return True


def _load_typical() -> int:
    """Fill counts with the 4-week rolling average for the selected rep."""
    rep = st.session_state.get("draft_rep", "")
    if not rep:
        return 0
    rows = get_daily_totals(week_start(date.today() - timedelta(days=28)),
                            week_start(date.today() - timedelta(days=7)), rep)
    if not rows:
        return 0
    for f in COUNT_FIELDS:
        val = round(sum(r.get(f, 0) for r in rows) / len(rows))
        st.session_state[f] = val
        st.session_state["_draft"][f] = val
    return len(rows)


# ══════════════════════════════════════════════════════════════════════════════
# Wizard — shared widget helpers
# ══════════════════════════════════════════════════════════════════════════════

def _card_header(icon: str, title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="card-hdr">'
        f'  <span class="card-hdr-icon">{icon}</span>'
        f'  <div>'
        f'    <div class="card-hdr-title">{title}</div>'
        f'    <div class="card-hdr-sub">{subtitle}</div>'
        f'  </div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _count_input(field: str, col=None) -> None:
    channel, outcome = FIELD_MAP[field]
    wts = get_weights()
    wt  = wts.get(channel, {}).get(outcome, 0)
    desc     = OUTCOME_HELP.get(field, "")
    help_txt = f"**{wt} pts each**\n\n{desc}"
    target   = col or st

    target.number_input(
        FIELD_LABELS[field],
        key=field,
        min_value=0,
        step=1,
        help=help_txt,
    )


def _proof_section(step_name: str) -> None:
    with st.expander("📎 Upload proof screenshots (optional)"):
        uploaded = st.file_uploader(
            "PNG / JPG / WebP",
            type=["png", "jpg", "jpeg", "webp"],
            accept_multiple_files=True,
            key=f"upload_{step_name}",
        )
        if uploaded:
            d_str = str(st.session_state.get("draft_date", date.today()))
            rep_s = re.sub(r"\W+", "_", str(st.session_state.get("draft_rep", "rep")))
            for uf in uploaded:
                fk = f"{uf.name}_{uf.size}"
                if fk not in st.session_state.proof_keys[step_name]:
                    ts    = datetime.now().strftime("%H%M%S%f")
                    safe  = re.sub(r"[^\w.]", "_", uf.name)
                    fpath = os.path.join(_UPLOAD_DIR, f"{d_str}_{rep_s}_{step_name}_{ts}_{safe}")
                    with open(fpath, "wb") as out:
                        out.write(uf.getbuffer())
                    st.session_state.draft_proofs[step_name].append(fpath)
                    st.session_state.proof_keys[step_name].add(fk)

        paths = st.session_state.draft_proofs.get(step_name, [])
        if paths:
            st.caption(f"✅ {len(paths)} file(s) saved for this step")
            tcols = st.columns(min(len(paths), 5))
            for i, p in enumerate(paths):
                if os.path.exists(p):
                    tcols[i % 5].image(p, width=120, caption=os.path.basename(p)[:22])


# ══════════════════════════════════════════════════════════════════════════════
# Wizard — stepper + live score panel
# ══════════════════════════════════════════════════════════════════════════════

def _render_stepper(current: int) -> None:
    """Visual HTML stepper bar, then a compact icon-button row for jumping."""
    steps_html = ""
    for i, (name, icon) in enumerate(zip(WIZARD_STEPS, STEP_ICONS)):
        state  = "done" if i < current else ("active" if i == current else "pending")
        circle = "✓"    if i < current else str(i + 1)
        steps_html += (
            f'<div class="wiz-step {state}">'
            f'  <div class="wiz-circle">{circle}</div>'
            f'  <div class="wiz-label">{icon} {name}</div>'
            f'</div>'
        )
        if i < len(WIZARD_STEPS) - 1:
            line = "done" if i < current else "pending"
            steps_html += f'<div class="wiz-line {line}"></div>'

    st.markdown(f'<div class="wiz-stepper">{steps_html}</div>', unsafe_allow_html=True)

    # Compact icon-only jump buttons
    st.markdown('<div class="step-jump-row">', unsafe_allow_html=True)
    jcols = st.columns(len(WIZARD_STEPS))
    for i, (col, icon) in enumerate(zip(jcols, STEP_ICONS)):
        is_current = i == current
        if i < 4:
            _sd2 = st.session_state.get("_draft", {})
            n = sum(1 for f in STEP_FIELDS[STEP_NAMES[i]]
                    if _sd2.get(f, 0) > 0)
            label = f"{icon}" + (f" ·{n}" if n else "")
        else:
            label = icon
        with col:
            if st.button(label, key=f"step_btn_{i}",
                         type="primary" if is_current else "secondary",
                         use_container_width=True,
                         help=WIZARD_STEPS[i]):
                st.session_state["_step_errors"] = []
                st.session_state["_error_step"] = ""
                st.session_state.wizard_step = i
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    # Step counter
    st.markdown(
        f'<div class="step-counter">'
        f'Step <span class="step-counter-accent">{current + 1}</span>'
        f'&nbsp;of&nbsp;{len(WIZARD_STEPS)}'
        f'&nbsp;·&nbsp;{WIZARD_STEPS[current]}'
        f'</div>',
        unsafe_allow_html=True,
    )


def _live_score_panel() -> None:
    """Right-side live scoring summary — reads widget state directly for real-time updates."""
    # Read directly from widget keys so score updates as inputs change (no form submit needed)
    counts = {f: int(st.session_state.get(f, 0) or 0) for f in COUNT_FIELDS}
    w, c   = get_weights(), {}
    s      = compute_row_score(counts, w, c)
    total  = s["total"]
    qr     = s["quality_ratio"]
    chs    = get_channels()

    with st.container(border=True):
        # Total score + threshold badge
        _badge_rep = st.session_state.get("draft_rep", "")
        _badge_tgt = _get_rep_targets(_badge_rep) if _badge_rep else {}
        _tgt_score = sum(
            int(_badge_tgt.get(f, 0)) * w.get(FIELD_MAP[f][0], {}).get(FIELD_MAP[f][1], 0)
            for f in COUNT_FIELDS if int(_badge_tgt.get(f, 0) or 0) > 0
        )
        if _tgt_score > 0:
            _ratio = total / _tgt_score
            if _ratio >= 1.2:   _badge, _bclr = "Elite",    "#10B981"
            elif _ratio >= 0.8: _badge, _bclr = "On Track",  "#F59E0B"
            else:               _badge, _bclr = "Building",  "#64748B"
        elif total >= 500:      _badge, _bclr = "Elite",    "#10B981"
        elif total >= 200:      _badge, _bclr = "On Track",  "#F59E0B"
        elif total > 0:         _badge, _bclr = "Building",  "#64748B"
        else:                   _badge, _bclr = None, None

        _badge_html = (
            f'<div style="display:inline-block;background:rgba(0,0,0,0.25);'
            f'color:{_bclr};border:1px solid {_bclr}44;border-radius:5px;'
            f'font-size:0.62rem;font-weight:800;letter-spacing:0.1em;'
            f'padding:2px 8px;text-transform:uppercase;margin-top:5px">'
            f'{_badge}</div>'
        ) if _badge else ""
        st.markdown(
            f'<div class="lsp-total-sub">'
            f'  {_svg("lightning", 13, "#64748B")} Live Score'
            f'</div>'
            f'<div class="lsp-total">{total}</div>'
            f'<div class="lsp-total-sub" style="margin-top:2px">points</div>'
            f'{_badge_html}',
            unsafe_allow_html=True,
        )
        # Quality ratio progress bar
        st.markdown(
            f'<div class="lsp-prog-track">'
            f'  <div class="lsp-prog-fill" style="width:{min(qr * 100, 100):.0f}%"></div>'
            f'</div>'
            f'<div class="lsp-qr-badge">{_svg("star", 12, "#10B981")} {qr:.0%} quality</div>',
            unsafe_allow_html=True,
        )
        # Channel breakdown — mini progress bars with SVG icons
        st.markdown(
            f'<div class="lsp-sec">{_svg("chart", 11, "#64748B")} By Channel</div>',
            unsafe_allow_html=True,
        )
        ch_totals = s["channel_totals"]
        max_ch    = max(ch_totals.values(), default=1) or 1
        bars_html = ""
        for ch in chs:
            pts = ch_totals.get(ch, 0)
            pct = min(pts / max_ch * 100, 100) if max_ch > 0 else 0
            ico = _CH_SVG.get(ch, lambda _=14: "•")(14)
            bars_html += (
                f'<div class="ch-bar-wrap">'
                f'  <span class="ch-bar-label">{ico}&nbsp;{ch}</span>'
                f'  <div class="ch-bar-track">'
                f'    <div class="ch-bar-fill" style="width:{pct:.0f}%"></div>'
                f'  </div>'
                f'  <span class="ch-bar-pts">{pts:.0f}</span>'
                f'</div>'
            )
        st.markdown(f'<div>{bars_html}</div>', unsafe_allow_html=True)

        # Step completion status with SVG
        _STEP_ICON_NAMES = ["calendar", "phone", "envelope", "link"]
        st.markdown(
            f'<div class="lsp-sec">{_svg("check", 11, "#64748B")} Steps filled</div>',
            unsafe_allow_html=True,
        )
        icons_html = ""
        for i, icon_name in enumerate(_STEP_ICON_NAMES):
            filled = any(st.session_state.get(f, 0) > 0 for f in STEP_FIELDS[STEP_NAMES[i]])
            color  = BRAND_GREEN if filled else "rgba(255,255,255,0.2)"
            icons_html += f'<span style="margin-right:6px">{_svg(icon_name, 18, color)}</span>'
        st.markdown(f'<div class="lsp-step-icons">{icons_html}</div>', unsafe_allow_html=True)

        # Score reasoning
        with st.expander("Score explained", expanded=False):
            insights = _score_reasoning(counts, s)
            for line in insights:
                st.markdown(f"- {line}")

        # Learn more — visual outcome weights
        with st.expander("How scoring works", expanded=False):
            _lm_ws    = get_weights()
            _lm_max   = max((p for ch in _lm_ws.values() for p in ch.values()), default=1)
            _lm_icons = {"Call": "phone", "Email": "envelope",
                         "LinkedIn": "link", "Meeting": "calendar"}
            _lm_html  = (
                '<div style="font-size:0.72rem;color:#64748B;line-height:1.55;'
                'margin-bottom:12px">'
                'Each activity earns <strong style="color:#94A3B8">points = count × weight</strong>. '
                'Longer bars = more points per activity.'
                '</div>'
            )
            for ch, outcomes in _lm_ws.items():
                _ico = _lm_icons.get(ch, "star")
                _lm_html += (
                    f'<div style="display:flex;align-items:center;gap:5px;'
                    f'margin:12px 0 5px 0">'
                    f'  {_svg(_ico, 13, "#64748B")}'
                    f'  <span style="font-size:0.65rem;font-weight:700;color:#475569;'
                    f'      text-transform:uppercase;letter-spacing:0.09em">{ch}</span>'
                    f'</div>'
                )
                for outcome, pts in outcomes.items():
                    _bw  = pts / _lm_max * 100
                    _bc  = "#10B981" if pts >= 30 else ("#F59E0B" if pts >= 10 else "#94A3B8")
                    _lm_html += (
                        f'<div style="display:flex;align-items:center;gap:7px;margin-bottom:5px">'
                        f'  <span style="font-size:0.73rem;color:#94A3B8;width:140px;'
                        f'      flex-shrink:0;white-space:nowrap;overflow:hidden;'
                        f'      text-overflow:ellipsis">{outcome}</span>'
                        f'  <div style="flex:1;height:5px;background:rgba(255,255,255,0.06);'
                        f'      border-radius:3px;overflow:hidden">'
                        f'    <div style="width:{_bw:.0f}%;height:100%;background:{_bc};'
                        f'        border-radius:3px"></div>'
                        f'  </div>'
                        f'  <span style="font-size:0.72rem;font-weight:700;color:{_bc};'
                        f'      width:32px;text-align:right;flex-shrink:0">{pts}</span>'
                        f'</div>'
                    )
            _lm_html += (
                '<div style="margin-top:12px;padding:8px 10px;border-radius:7px;'
                'background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07)">'
                f'  <span style="font-size:0.68rem;font-weight:700;color:#475569;'
                f'      text-transform:uppercase;letter-spacing:0.08em">'
                f'    {_svg("star",11,"#475569")} Quality Ratio&nbsp;</span>'
                '<span style="font-size:0.72rem;color:#64748B">'
                '= green-tier pts ÷ total. Aim for 50%+.</span>'
                '</div>'
            )
            st.markdown(_lm_html, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# Wizard — step renderers
# ══════════════════════════════════════════════════════════════════════════════

def _step_meetings() -> None:
    _card_header(_svg("calendar", 22, "#94A3B8"), "Meetings", "How many meetings did you hold this week?")
    c1, _ = st.columns(2)
    _count_input("meeting_held", col=c1)
    st.markdown("")
    _, nav_r = st.columns(2)
    with nav_r:
        next_clicked = st.button("Next →", type="primary", use_container_width=True, key="meet_next")
    _proof_section("meetings")
    if next_clicked:
        st.session_state["_draft"]["meeting_held"] = int(st.session_state.get("meeting_held", 0) or 0)
        st.session_state["_step_errors"] = []
        st.session_state["_error_step"] = ""
        st.session_state.wizard_step += 1
        st.rerun()


def _step_calls() -> None:
    _card_header(_svg("phone", 22, "#94A3B8"), "Calls", "Log every call attempt and outcome from your sessions this week.")
    _errors = st.session_state.get("_step_errors", []) if st.session_state.get("_error_step") == "calls" else []
    c1, c2 = st.columns(2)
    for i, f in enumerate(STEP_FIELDS["calls"]):
        _count_input(f, col=c1 if i % 2 == 0 else c2)
    st.markdown("")
    if _errors:
        err_html = "".join(f'<div class="funnel-err-item">↳ {e}</div>' for e in _errors)
        st.markdown(
            f'<div class="funnel-err-box">'
            f'<div class="funnel-err-title">⚠ Funnel Constraint Violated</div>'
            f'{err_html}</div>',
            unsafe_allow_html=True,
        )
        autofix_clicked = st.button("🔧 Auto-fix Calls", type="secondary", use_container_width=True, key="autofix_calls")
    else:
        autofix_clicked = False
    nav_l, nav_r = st.columns(2)
    with nav_l:
        prev_clicked = st.button("← Previous", use_container_width=True, key="calls_prev")
    with nav_r:
        next_clicked = st.button("Next →", type="primary", use_container_width=True, key="calls_next")
    _proof_section("calls")
    if autofix_clicked:
        _c = {f: int(st.session_state.get(f, 0) or 0) for f in STEP_FIELDS["calls"]}
        for f, v in autofix_step("calls", _c).items():
            st.session_state[f] = v
            st.session_state["_draft"][f] = v
        st.session_state["_step_errors"] = []
        st.session_state["_error_step"] = ""
        st.rerun()
    elif prev_clicked:
        for f in STEP_FIELDS["calls"]:
            st.session_state["_draft"][f] = int(st.session_state.get(f, 0) or 0)
        st.session_state["_step_errors"] = []
        st.session_state["_error_step"] = ""
        st.session_state.wizard_step -= 1
        st.rerun()
    elif next_clicked:
        _c = {f: int(st.session_state.get(f, 0) or 0) for f in STEP_FIELDS["calls"]}
        _errs = validate_step("calls", _c)
        if _errs:
            st.session_state["_step_errors"] = _errs
            st.session_state["_error_step"] = "calls"
            st.rerun()
        else:
            for f in STEP_FIELDS["calls"]:
                st.session_state["_draft"][f] = int(st.session_state.get(f, 0) or 0)
            st.session_state["_step_errors"] = []
            st.session_state["_error_step"] = ""
            st.session_state.wizard_step += 1
            st.rerun()


def _step_email() -> None:
    _card_header(_svg("envelope", 22, "#94A3B8"), "Email", "Count every outbound email and any replies you received this week.")
    _errors = st.session_state.get("_step_errors", []) if st.session_state.get("_error_step") == "email" else []
    c1, c2 = st.columns(2)
    for i, f in enumerate(STEP_FIELDS["email"]):
        _count_input(f, col=c1 if i % 2 == 0 else c2)
    st.markdown("")
    if _errors:
        err_html = "".join(f'<div class="funnel-err-item">↳ {e}</div>' for e in _errors)
        st.markdown(
            f'<div class="funnel-err-box">'
            f'<div class="funnel-err-title">⚠ Funnel Constraint Violated</div>'
            f'{err_html}</div>',
            unsafe_allow_html=True,
        )
        autofix_clicked = st.button("🔧 Auto-fix Email", type="secondary", use_container_width=True, key="autofix_email")
    else:
        autofix_clicked = False
    nav_l, nav_r = st.columns(2)
    with nav_l:
        prev_clicked = st.button("← Previous", use_container_width=True, key="email_prev")
    with nav_r:
        next_clicked = st.button("Next →", type="primary", use_container_width=True, key="email_next")
    _proof_section("email")
    if autofix_clicked:
        _c = {f: int(st.session_state.get(f, 0) or 0) for f in STEP_FIELDS["email"]}
        for f, v in autofix_step("email", _c).items():
            st.session_state[f] = v
            st.session_state["_draft"][f] = v
        st.session_state["_step_errors"] = []
        st.session_state["_error_step"] = ""
        st.rerun()
    elif prev_clicked:
        for f in STEP_FIELDS["email"]:
            st.session_state["_draft"][f] = int(st.session_state.get(f, 0) or 0)
        st.session_state["_step_errors"] = []
        st.session_state["_error_step"] = ""
        st.session_state.wizard_step -= 1
        st.rerun()
    elif next_clicked:
        _c = {f: int(st.session_state.get(f, 0) or 0) for f in STEP_FIELDS["email"]}
        _errs = validate_step("email", _c)
        if _errs:
            st.session_state["_step_errors"] = _errs
            st.session_state["_error_step"] = "email"
            st.rerun()
        else:
            for f in STEP_FIELDS["email"]:
                st.session_state["_draft"][f] = int(st.session_state.get(f, 0) or 0)
            st.session_state["_step_errors"] = []
            st.session_state["_error_step"] = ""
            st.session_state.wizard_step += 1
            st.rerun()


def _step_linkedin() -> None:
    _card_header(_svg("link", 22, "#94A3B8"), "LinkedIn", "Record all LinkedIn outreach activity from this week.")
    _errors = st.session_state.get("_step_errors", []) if st.session_state.get("_error_step") == "linkedin" else []
    c1, c2 = st.columns(2)
    for i, f in enumerate(STEP_FIELDS["linkedin"]):
        _count_input(f, col=c1 if i % 2 == 0 else c2)
    st.markdown("")
    if _errors:
        err_html = "".join(f'<div class="funnel-err-item">↳ {e}</div>' for e in _errors)
        st.markdown(
            f'<div class="funnel-err-box">'
            f'<div class="funnel-err-title">⚠ Funnel Constraint Violated</div>'
            f'{err_html}</div>',
            unsafe_allow_html=True,
        )
        autofix_clicked = st.button("🔧 Auto-fix LinkedIn", type="secondary", use_container_width=True, key="autofix_li")
    else:
        autofix_clicked = False
    nav_l, nav_r = st.columns(2)
    with nav_l:
        prev_clicked = st.button("← Previous", use_container_width=True, key="li_prev")
    with nav_r:
        next_clicked = st.button("Review & Save →", type="primary", use_container_width=True, key="li_next")
    _proof_section("linkedin")
    if autofix_clicked:
        _c = {f: int(st.session_state.get(f, 0) or 0) for f in STEP_FIELDS["linkedin"]}
        for f, v in autofix_step("linkedin", _c).items():
            st.session_state[f] = v
            st.session_state["_draft"][f] = v
        st.session_state["_step_errors"] = []
        st.session_state["_error_step"] = ""
        st.rerun()
    elif prev_clicked:
        for f in STEP_FIELDS["linkedin"]:
            st.session_state["_draft"][f] = int(st.session_state.get(f, 0) or 0)
        st.session_state["_step_errors"] = []
        st.session_state["_error_step"] = ""
        st.session_state.wizard_step -= 1
        st.rerun()
    elif next_clicked:
        _c = {f: int(st.session_state.get(f, 0) or 0) for f in STEP_FIELDS["linkedin"]}
        _errs = validate_step("linkedin", _c)
        if _errs:
            st.session_state["_step_errors"] = _errs
            st.session_state["_error_step"] = "linkedin"
            st.rerun()
        else:
            for f in STEP_FIELDS["linkedin"]:
                st.session_state["_draft"][f] = int(st.session_state.get(f, 0) or 0)
            st.session_state["_step_errors"] = []
            st.session_state["_error_step"] = ""
            st.session_state.wizard_step += 1
            st.rerun()


def _step_review() -> None:
    _rv_date_raw = st.session_state.get("draft_date", date.today())
    if isinstance(_rv_date_raw, str):
        _rv_date_raw = date.fromisoformat(_rv_date_raw)
    date_val = str(week_start(_rv_date_raw))
    rep_name = st.session_state.get("draft_rep", "")
    _d       = st.session_state.get("_draft", {})
    counts   = {f: int(_d.get(f, 0) or 0) for f in COUNT_FIELDS}
    w, c     = get_weights(), {}
    scored   = compute_row_score(counts, w, c)

    funnel_result = validate_all(counts)
    _funnel_ok    = not has_errors(funnel_result)

    # ── Receipt-style header ───────────────────────────────────────────────────
    qr_color = "#10B981" if scored["quality_ratio"] >= 0.5 else BRAND_AMBER
    st.markdown(
        f'<div class="receipt-header">'
        f'  <div>'
        f'    <div class="receipt-title">✅ Review &amp; Save</div>'
        f'    <div class="receipt-meta">'
        f'      {rep_name or "<em>No rep selected</em>"}&nbsp;·&nbsp;Week of {date_val}'
        f'    </div>'
        f'  </div>'
        f'  <div style="text-align:right">'
        f'    <div class="receipt-score-lbl">Total Score</div>'
        f'    <div class="receipt-score">{scored["total"]}</div>'
        f'    <div class="receipt-qr" style="color:{qr_color}">'
        f'      {scored["quality_ratio"]:.0%}&nbsp;quality ratio'
        f'    </div>'
        f'  </div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Per-channel breakdown ──────────────────────────────────────────────────
    st.markdown('<div class="sec-label">Score Breakdown</div>', unsafe_allow_html=True)
    any_data = False
    for ch in get_channels():
        ch_fields = [f for f, (chan, _) in FIELD_MAP.items() if chan == ch]
        ch_rows   = [(f, scored["fields"].get(f, {})) for f in ch_fields
                     if (scored["fields"].get(f, {}).get("count", 0) > 0
                         or scored["fields"].get(f, {}).get("capped"))]
        if not ch_rows:
            continue
        any_data   = True
        ch_total   = scored["channel_totals"].get(ch, 0)
        ico        = CHANNEL_ICONS.get(ch, "•")
        rows_html  = ""
        for f, fd in ch_rows:
            cap_note = (f'<span class="rev-capped">  ⚠️ capped — {fd["effective"]} counted</span>'
                        if fd.get("capped") else "")
            rows_html += (
                f'<tr>'
                f'  <td>{FIELD_LABELS[f]}{cap_note}</td>'
                f'  <td style="text-align:center;color:#94A3B8">{fd["count"]} × {fd["weight"]:.0f}</td>'
                f'  <td class="rev-pts">{fd["points"]:.0f}</td>'
                f'</tr>'
            )
        st.markdown(
            f'<div class="rev-ch-hdr">'
            f'  <span>{ico} {ch}</span>'
            f'  <span class="rev-ch-pts">{ch_total:.1f} pts</span>'
            f'</div>'
            f'<table class="rev-table">{rows_html}</table>',
            unsafe_allow_html=True,
        )

    if not any_data:
        st.info("No counts entered yet — use the steps above to fill in your activity.")

    # ── vs. Weekly Targets ─────────────────────────────────────────────────────
    _tgt = _get_rep_targets(rep_name)
    _tgt_fields = [f for f in COUNT_FIELDS if _tgt.get(f, 0) > 0]
    if _tgt_fields:
        st.markdown('<div class="sec-label">vs. Weekly Targets</div>', unsafe_allow_html=True)
        met_count = 0
        tgt_rows_html = ""
        for f in _tgt_fields:
            t = int(_tgt.get(f, 0))
            a = counts.get(f, 0)
            pct = min(a / t * 100, 100) if t > 0 else 0
            met = a >= t
            if met:
                met_count += 1
            status_icon = "✅" if met else ("🟡" if a > 0 else "⬜")
            bar_color = "#10B981" if met else ("#F59E0B" if a > 0 else "rgba(255,255,255,0.12)")
            tgt_rows_html += (
                f'<tr>'
                f'  <td style="color:#94A3B8;padding:7px 0">{FIELD_LABELS[f]}</td>'
                f'  <td style="text-align:center;color:#F8FAFC;font-weight:700;padding:7px 4px">{a}</td>'
                f'  <td style="text-align:center;color:#64748B;padding:7px 4px">{t}</td>'
                f'  <td style="padding:7px 4px;width:120px">'
                f'    <div style="height:5px;background:rgba(255,255,255,0.08);border-radius:3px;overflow:hidden">'
                f'      <div style="width:{pct:.0f}%;height:100%;background:{bar_color};border-radius:3px"></div>'
                f'    </div>'
                f'  </td>'
                f'  <td style="text-align:center;font-size:0.9rem;padding:7px 0">{status_icon}</td>'
                f'</tr>'
            )
        _th = 'style="text-align:left;font-size:0.65rem;color:#64748B;text-transform:uppercase;letter-spacing:0.07em;padding:4px 0"'
        _thc = 'style="text-align:center;font-size:0.65rem;color:#64748B;text-transform:uppercase;letter-spacing:0.07em;padding:4px 0"'
        st.markdown(
            f'<table style="width:100%;border-collapse:collapse;font-size:0.82rem">'
            f'  <thead><tr>'
            f'    <th {_th}>Outcome</th>'
            f'    <th {_thc}>Actual</th>'
            f'    <th {_thc}>Target</th>'
            f'    <th {_th}>Progress</th>'
            f'    <th {_thc}>Status</th>'
            f'  </tr></thead>'
            f'  <tbody>{tgt_rows_html}</tbody>'
            f'</table>',
            unsafe_allow_html=True,
        )
        _tgt_pct = met_count / len(_tgt_fields) * 100
        _summary_color = "#10B981" if _tgt_pct == 100 else ("#F59E0B" if _tgt_pct >= 50 else "#EF4444")
        st.markdown(
            f'<div style="font-size:0.82rem;color:{_summary_color};font-weight:700;margin-top:8px">'
            f'  {met_count} of {len(_tgt_fields)} targets met&nbsp;·&nbsp;{_tgt_pct:.0f}%'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ── Proofs summary ─────────────────────────────────────────────────────────
    total_proofs = sum(len(v) for v in st.session_state.draft_proofs.values())
    if total_proofs:
        with st.expander(f"📎 {total_proofs} proof file(s) attached"):
            for sname in STEP_NAMES:
                paths = st.session_state.draft_proofs[sname]
                if paths:
                    st.markdown(f"**{sname.title()}:**")
                    tcols = st.columns(min(len(paths), 5))
                    for i, p in enumerate(paths):
                        if os.path.exists(p):
                            tcols[i % 5].image(p, width=120, caption=os.path.basename(p)[:22])

    # ── Notes + existing-row warning ───────────────────────────────────────────
    st.text_area("Week notes (optional)", key="draft_notes", height=75)

    existing = get_existing_row(date_val, rep_name)
    add_to   = False
    if existing:
        st.info(
            f"📝 Updating existing record for **{rep_name}** — week of **{date_val}**. "
            f"The counts below already include what was previously saved — just edit and save."
        )

    # ── Funnel violations (blocks Save) ────────────────────────────────────────
    if not _funnel_ok:
        all_v = [
            (step.title(), err)
            for step, errs in funnel_result.items()
            for err in errs
        ]
        err_items = "".join(
            f'<div class="funnel-err-item">↳ <strong>{step}:</strong> {err}</div>'
            for step, err in all_v
        )
        st.markdown(
            f'<div class="funnel-err-box">'
            f'<div class="funnel-err-title">⚠ Funnel Violations — Fix before saving</div>'
            f'{err_items}</div>',
            unsafe_allow_html=True,
        )
        if st.button("🔧 Auto-fix All Violations", key="autofix_review",
                     type="secondary", use_container_width=True):
            fixed = autofix_all(counts)
            for f, v in fixed.items():
                st.session_state[f] = v
                st.session_state["_draft"][f] = v
            st.rerun()

    # ── Action buttons ─────────────────────────────────────────────────────────
    st.markdown("")
    b1, b2, b3 = st.columns(3)
    with b1:
        if st.button("← Back", use_container_width=True, key="rev_back"):
            st.session_state.wizard_step = 3; st.rerun()
    with b2:
        if st.button("💾 Save Week", type="primary", use_container_width=True, key="rev_save",
                     disabled=not _funnel_ok,
                     help="Fix funnel violations above before saving" if not _funnel_ok else None):
            if not rep_name:
                st.error("No rep selected — pick a rep in the left sidebar.")
            else:
                notes  = st.session_state.get("draft_notes", "")
                row_id = upsert_daily_total(date_val, rep_name, counts, notes, add_to)
                for sname in STEP_NAMES:
                    add_proofs(row_id, sname, st.session_state.draft_proofs[sname])
                action = "Updated" if existing else "Saved"
                st.success(f"✅  {action}! **{rep_name}** — week of **{date_val}** — "
                           f"**{scored['total']} pts**")
                _clear_draft()
                st.rerun()
    with b3:
        if st.button("🗑️ Clear Draft", use_container_width=True, key="rev_clear"):
            _clear_draft(); st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# Dashboard helpers
# ══════════════════════════════════════════════════════════════════════════════

def _render_leaderboard(lb_rows: list, selected_rep: str) -> None:
    chs = get_channels()
    ch_ths = "".join(f"<th>{CHANNEL_ICONS.get(ch,'')}&nbsp;{ch}</th>" for ch in chs)

    _MEDALS     = ["🥇", "🥈", "🥉"]
    _TOP_CLASSES = ["lb-gold", "lb-silver", "lb-bronze"]
    rows_html = ""
    for i, row in enumerate(lb_rows):
        is_sel     = selected_rep not in ("All", "") and row["Rep"] == selected_rep
        top_cls    = _TOP_CLASSES[i] if i < 3 else ""
        tr_class   = " ".join(filter(None, ["lb-sel" if is_sel else "", top_cls]))
        ch_tds     = "".join(
            f'<td style="text-align:right">{row.get(f"{ch} Pts", 0)}</td>' for ch in chs
        )
        rank_display = _MEDALS[i] if i < 3 else row["Rank"]
        rows_html += (
            f'<tr class="{tr_class}">'
            f'  <td class="lb-rank">{rank_display}</td>'
            f'  <td class="lb-rep">{row["Rep"]}</td>'
            f'  <td class="lb-score" style="text-align:right">{row["Score"]}</td>'
            f'  {ch_tds}'
            f'  <td class="lb-qr" style="text-align:right">{row["Quality Ratio"]}</td>'
            f'</tr>'
        )

    st.markdown(
        f'<div class="lb-wrap">'
        f'<table class="lb-table">'
        f'  <thead><tr>'
        f'    <th>#</th><th>Rep</th>'
        f'    <th style="text-align:right">Score</th>'
        f'    {ch_ths}'
        f'    <th style="text-align:right">Quality</th>'
        f'  </tr></thead>'
        f'  <tbody>{rows_html}</tbody>'
        f'</table></div>',
        unsafe_allow_html=True,
    )
    st.caption("Quality Ratio = high-value pts ÷ total pts.  High-value = uncapped outcomes.")


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    # Branding
    st.markdown(
        '<div class="sb-logo">'
        '  <span class="sb-logo-icon">🎯</span>'
        '  <div>'
        '    <div class="sb-logo-name">RWS Sales Tracker</div>'
        '    <div class="sb-logo-sub">Weekly Activity Log</div>'
        '    <span class="sb-logo-badge">RWS</span>'
        '  </div>'
        '</div>',
        unsafe_allow_html=True,
    )

    # ── Log context ────────────────────────────────────────────────────────────
    st.markdown('<div class="sb-section">Rep</div>', unsafe_allow_html=True)
    _reps = get_setting("reps", [])
    if _reps:
        st.selectbox("Rep", _reps, key="draft_rep", label_visibility="collapsed")
    else:
        st.warning("No reps — add them in ⚙️ Settings")

    # ── Week picker ────────────────────────────────────────────────────────────
    st.markdown('<div class="sb-section">Week</div>', unsafe_allow_html=True)
    _today   = date.today()
    _cur_mon = week_start(_today)
    # 23 weeks back → this week → 4 weeks ahead (28 options)
    _wk_list = [_cur_mon + timedelta(weeks=i) for i in range(-23, 5)]

    def _wk_lbl(w: date) -> str:
        end = w + timedelta(days=4)
        s = f"{w.strftime('%d %b')} – {end.strftime('%d %b %Y')}"
        return (s + "  ← now") if w == _cur_mon else s

    _wk_labels   = [_wk_lbl(w) for w in _wk_list]
    _label_to_wk = dict(zip(_wk_labels, _wk_list))

    _cur_draft = st.session_state.get("draft_date", _cur_mon)
    if isinstance(_cur_draft, str):
        _cur_draft = date.fromisoformat(_cur_draft)
    _cur_draft_wk = week_start(_cur_draft)
    _def_idx = next((i for i, w in enumerate(_wk_list) if w == _cur_draft_wk), 23)

    _sel_label = st.selectbox(
        "Week", _wk_labels, index=_def_idx,
        label_visibility="collapsed", key="week_sel",
    )
    _new_wk = _label_to_wk[_sel_label]
    if st.session_state.get("draft_date") != _new_wk:
        st.session_state["draft_date"] = _new_wk
        st.session_state["_loaded_for"] = None

    # ── Draft score indicator ──────────────────────────────────────────────────
    _sd = st.session_state.get("_draft", {})
    _draft_counts = {f: int(_sd.get(f, 0) or 0) for f in COUNT_FIELDS}
    _draft_total  = sum_scores([_draft_counts]) if any(v > 0 for v in _draft_counts.values()) else 0
    if _draft_total > 0:
        st.markdown(
            f'<div class="sb-draft-score">{_draft_total}</div>'
            f'<div class="sb-draft-label">pts in current draft</div>',
            unsafe_allow_html=True,
        )
        if st.button("→ Review & Save", type="primary", use_container_width=True,
                     key="sb_review"):
            st.session_state.wizard_step = 4; st.rerun()

    # ── Weekly Progress ────────────────────────────────────────────────────────
    _sb_tgt_settings = _get_rep_targets(st.session_state.get("draft_rep", ""))
    _sb_tgt_active   = {f: int(_sb_tgt_settings.get(f, 0) or 0)
                        for f in COUNT_FIELDS
                        if int(_sb_tgt_settings.get(f, 0) or 0) > 0}
    if _sb_tgt_active:
        st.markdown('<div class="sb-section">Weekly Progress</div>', unsafe_allow_html=True)
        # Load the saved record for the selected rep + week (not the draft)
        _sb_rep_p = st.session_state.get("draft_rep", "")
        _sb_dr    = st.session_state.get("draft_date", date.today())
        if isinstance(_sb_dr, str):
            _sb_dr = date.fromisoformat(_sb_dr)
        _sb_saved = (get_existing_row(str(week_start(_sb_dr)), _sb_rep_p)
                     if _sb_rep_p else None) or {}

        _CH_GROUPS = [("📅", "meetings"), ("📞", "calls"), ("✉️", "email"), ("🔗", "linkedin")]
        prog_html  = ""
        total_met  = 0
        for ico, step in _CH_GROUPS:
            ch_fields = [f for f in STEP_FIELDS[step] if f in _sb_tgt_active]
            if not ch_fields:
                continue
            prog_html += (
                f'<div style="font-size:0.66rem;font-weight:700;color:#475569;'
                f'margin:10px 0 5px 0;text-transform:uppercase;letter-spacing:0.07em">'
                f'{ico} {step.title()}</div>'
            )
            for f in ch_fields:
                t   = _sb_tgt_active[f]
                a   = int(_sb_saved.get(f, 0) or 0)
                pct = min(a / t * 100, 100) if t > 0 else 0
                met = a >= t
                if met:
                    total_met += 1
                val_color = "#10B981" if met else ("#F8FAFC" if a > 0 else "#475569")
                bar_color = "#10B981" if met else ("#F59E0B" if a > 0 else "rgba(255,255,255,0.08)")
                prog_html += (
                    f'<div style="margin-bottom:8px">'
                    f'  <div style="display:flex;justify-content:space-between;'
                    f'      align-items:center;margin-bottom:3px">'
                    f'    <span style="font-size:0.71rem;color:#94A3B8;overflow:hidden;'
                    f'        text-overflow:ellipsis;white-space:nowrap;max-width:118px">'
                    f'      {FIELD_LABELS[f]}</span>'
                    f'    <span style="font-size:0.71rem;font-weight:700;color:{val_color};'
                    f'        white-space:nowrap;margin-left:4px">'
                    f'      {a}<span style="color:#334155;font-weight:400"> / {t}</span>'
                    f'    </span>'
                    f'  </div>'
                    f'  <div style="height:4px;background:rgba(255,255,255,0.07);'
                    f'      border-radius:2px;overflow:hidden">'
                    f'    <div style="width:{pct:.0f}%;height:100%;background:{bar_color};'
                    f'        border-radius:2px"></div>'
                    f'  </div>'
                    f'</div>'
                )
        st.markdown(prog_html, unsafe_allow_html=True)
        # Summary line
        _n_tgt = len(_sb_tgt_active)
        _s_color = "#10B981" if total_met == _n_tgt else ("#F59E0B" if total_met > 0 else "#64748B")
        st.markdown(
            f'<div style="font-size:0.7rem;color:{_s_color};font-weight:700;'
            f'margin-top:4px;margin-bottom:2px">'
            f'  {total_met} / {_n_tgt} goals hit this week'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ── Quick actions ──────────────────────────────────────────────────────────
    st.markdown('<div class="sb-section">Quick Actions</div>', unsafe_allow_html=True)

    if st.button("⬛  Zero All Fields", use_container_width=True, key="sb_zero"):
        _zero_all(); st.rerun()

    if st.button("📋  Copy Last Week", use_container_width=True, key="sb_copy"):
        if _copy_last_week():
            st.toast("Copied from last week!", icon="✅")
        else:
            st.toast("No record found for last week.", icon="⚠️")
        st.rerun()

    if st.button("📈  Typical Week (4-wk avg)", use_container_width=True, key="sb_typical"):
        n = _load_typical()
        if n:
            st.toast(f"Loaded average of {n} week(s)", icon="📈")
        else:
            st.toast("Not enough history yet.", icon="⚠️")
        st.rerun()

    # ── Clear draft ────────────────────────────────────────────────────────────
    if _draft_total > 0:
        if st.button("🗑️  Clear Draft", use_container_width=True, key="sb_clear"):
            _clear_draft(); st.rerun()

    # ── Week start ─────────────────────────────────────────────────────────────
    st.markdown('<div class="sb-section">Week Start</div>', unsafe_allow_html=True)
    _ws_cur = get_setting("week_starts_monday", True)
    _ws_opt = st.radio("Week", ["Monday", "Sunday"],
                       index=0 if _ws_cur else 1,
                       horizontal=True, key="sb_week",
                       label_visibility="collapsed")
    _ws_new = _ws_opt == "Monday"
    if _ws_new != _ws_cur:
        set_setting("week_starts_monday", _ws_new)

# Auto-load existing record now that draft_rep + draft_date are set
_auto_load_existing()


# ══════════════════════════════════════════════════════════════════════════════
# App hero header (above tabs)
# ══════════════════════════════════════════════════════════════════════════════

_h_rep     = st.session_state.get("draft_rep", "")
_h_date_raw = st.session_state.get("draft_date", date.today())
if isinstance(_h_date_raw, str):
    _h_date_raw = date.fromisoformat(_h_date_raw)
_h_wk_start = week_start(_h_date_raw)
_h_wk_end   = _h_wk_start + timedelta(days=4)
_h_wk_str   = f"{_h_wk_start.strftime('%d %b')} – {_h_wk_end.strftime('%d %b %Y')}"
_h_meta = (
    f"<strong>{_h_rep}</strong>&nbsp;·&nbsp;Week of {_h_wk_str}"
    if _h_rep else f"Week of {_h_wk_str}"
)
st.markdown(
    f'<div class="app-hero">'
    f'  <div class="app-hero-eyebrow">RWS · Weekly Activity Tracker</div>'
    f'  <div class="app-hero-title">Sales Command Centre</div>'
    f'  <div class="app-hero-meta">{_h_meta}</div>'
    f'</div>',
    unsafe_allow_html=True,
)


# ══════════════════════════════════════════════════════════════════════════════
# Main tabs
# ══════════════════════════════════════════════════════════════════════════════

tab_wizard, tab_goals, tab_dash, tab_import, tab_settings = st.tabs(
    ["📝  Weekly Log", "🎯  Goals", "📈  Dashboard", "📤  Import CSV", "⚙️  Settings"]
)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — DAILY LOG WIZARD
# ══════════════════════════════════════════════════════════════════════════════

with tab_wizard:
    reps = get_setting("reps", [])
    if not reps:
        st.error("No reps configured. Open ⚙️ Settings to add rep names first.")
    else:
        _render_stepper(st.session_state.wizard_step)
        st.markdown("")

        form_col, score_col = st.columns([7, 3], gap="large")

        with form_col:
            with st.container(border=True):
                _step = st.session_state.wizard_step
                if   _step == 0: _step_meetings()
                elif _step == 1: _step_calls()
                elif _step == 2: _step_email()
                elif _step == 3: _step_linkedin()
                elif _step == 4: _step_review()

        with score_col:
            _live_score_panel()


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — GOALS
# ══════════════════════════════════════════════════════════════════════════════

with tab_goals:
    _g_rep      = st.session_state.get("draft_rep", "")
    _g_date_raw = st.session_state.get("draft_date", date.today())
    if isinstance(_g_date_raw, str):
        _g_date_raw = date.fromisoformat(_g_date_raw)
    _g_wk      = week_start(_g_date_raw)
    _g_wk_end  = _g_wk + timedelta(days=4)
    _g_wk_lbl  = f"{_g_wk.strftime('%d %b')} – {_g_wk_end.strftime('%d %b %Y')}"
    _cur_tgt   = _get_rep_targets(_g_rep) if _g_rep else {}

    # ── Header ─────────────────────────────────────────────────────────────────
    st.markdown(
        f'<div class="section-title">Weekly Goals</div>'
        f'<div class="section-title-sub">'
        f'  {(_g_rep + "  ·  ") if _g_rep else ""}Week of {_g_wk_lbl}'
        f'</div>',
        unsafe_allow_html=True,
    )

    goal_left, goal_right = st.columns([6, 4], gap="large")

    # ── Set your goals ─────────────────────────────────────────────────────────
    with goal_left:
        with st.container(border=True):
            st.markdown(
                f'<div class="card-hdr">'
                f'  <span class="card-hdr-icon">{_svg("target", 20, "#94A3B8")}</span>'
                f'  <div>'
                f'    <div class="card-hdr-title">Set Your Weekly Targets</div>'
                f'    <div class="card-hdr-sub">Leave at 0 to skip tracking for that activity</div>'
                f'  </div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            # ── Meetings row (1 field — slim full-width row) ────────────────────
            st.markdown(
                f'<div class="sec-label">{_svg("calendar",12,"#64748B")} Meetings</div>',
                unsafe_allow_html=True,
            )
            _m_cols = st.columns([1, 3])
            with _m_cols[0]:
                for f in STEP_FIELDS["meetings"]:
                    st.number_input(FIELD_LABELS[f], value=int(_cur_tgt.get(f, 0)),
                                    min_value=0, step=1, key=f"goal_{f}")

            # ── Calls + Email side by side ──────────────────────────────────────
            _ce_l, _ce_r = st.columns(2, gap="medium")
            with _ce_l:
                st.markdown(
                    f'<div class="sec-label">{_svg("phone",12,"#64748B")} Calls</div>',
                    unsafe_allow_html=True,
                )
                for f in STEP_FIELDS["calls"]:
                    st.number_input(FIELD_LABELS[f], value=int(_cur_tgt.get(f, 0)),
                                    min_value=0, step=1, key=f"goal_{f}")
            with _ce_r:
                st.markdown(
                    f'<div class="sec-label">{_svg("envelope",12,"#64748B")} Email</div>',
                    unsafe_allow_html=True,
                )
                for f in STEP_FIELDS["email"]:
                    st.number_input(FIELD_LABELS[f], value=int(_cur_tgt.get(f, 0)),
                                    min_value=0, step=1, key=f"goal_{f}")

            # ── LinkedIn row (4 fields in 2×2 grid) ────────────────────────────
            st.markdown(
                f'<div class="sec-label">{_svg("link",12,"#64748B")} LinkedIn</div>',
                unsafe_allow_html=True,
            )
            _li_l, _li_r = st.columns(2, gap="medium")
            for i, f in enumerate(STEP_FIELDS["linkedin"]):
                with (_li_l if i % 2 == 0 else _li_r):
                    st.number_input(FIELD_LABELS[f], value=int(_cur_tgt.get(f, 0)),
                                    min_value=0, step=1, key=f"goal_{f}")

            st.markdown("")
            if not _g_rep:
                st.warning("Select a rep in the sidebar to save goals.")
            elif st.button("💾 Save Goals", type="primary", use_container_width=True, key="save_goals"):
                _new_tgt = {f: int(st.session_state.get(f"goal_{f}", 0) or 0) for f in COUNT_FIELDS}
                _set_rep_targets(_g_rep, _new_tgt)
                st.success(f"✅  Goals saved for **{_g_rep}**!")
                st.rerun()

        # ── Notes ──────────────────────────────────────────────────────────────
        with st.container(border=True):
            st.markdown(
                f'<div class="card-hdr">'
                f'  <span class="card-hdr-icon">{_svg("book", 20, "#94A3B8")}</span>'
                f'  <div>'
                f'    <div class="card-hdr-title">Week Notes</div>'
                f'    <div class="card-hdr-sub">Context, blockers, wins — anything worth remembering</div>'
                f'  </div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            _g_saved_row   = get_existing_row(str(_g_wk), _g_rep) if _g_rep else None
            _g_saved_notes = (_g_saved_row or {}).get("notes", "")
            st.text_area("Notes", value=_g_saved_notes, height=120,
                         key="goals_notes", label_visibility="collapsed")
            if st.button("💾 Save Notes", use_container_width=True, key="save_goals_notes"):
                if not _g_rep:
                    st.error("Select a rep in the sidebar first.")
                else:
                    _g_counts = {f: int((_g_saved_row or {}).get(f, 0)) for f in COUNT_FIELDS}
                    upsert_daily_total(str(_g_wk), _g_rep, _g_counts,
                                       st.session_state.get("goals_notes", ""))
                    st.success("✅  Notes saved!")
                    st.rerun()

    # ── Progress this week ─────────────────────────────────────────────────────
    with goal_right:
        with st.container(border=True):
            st.markdown(
                f'<div class="card-hdr">'
                f'  <span class="card-hdr-icon">{_svg("trending", 20, "#94A3B8")}</span>'
                f'  <div>'
                f'    <div class="card-hdr-title">This Week\'s Progress</div>'
                f'    <div class="card-hdr-sub">Logged vs. your targets</div>'
                f'  </div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            _g_tgt_active = {f: int(_cur_tgt.get(f, 0)) for f in COUNT_FIELDS
                             if int(_cur_tgt.get(f, 0) or 0) > 0}

            if not _g_rep:
                st.info("Select a rep in the sidebar to view progress.")
            elif not _g_tgt_active:
                st.info("Set your targets on the left and hit Save Goals to start tracking.")
            else:
                _g_row    = get_existing_row(str(_g_wk), _g_rep)
                _g_actual = {f: int((_g_row or {}).get(f, 0)) for f in COUNT_FIELDS}

                _g_met   = sum(1 for f, t in _g_tgt_active.items() if _g_actual.get(f, 0) >= t)
                _g_total = len(_g_tgt_active)
                _g_pct   = _g_met / _g_total * 100 if _g_total else 0
                _g_col   = "#10B981" if _g_pct == 100 else ("#F59E0B" if _g_pct >= 50 else "#EF4444")

                # Summary metric
                st.markdown(
                    f'<div style="display:flex;align-items:baseline;gap:8px;margin-bottom:4px">'
                    f'  <span style="font-size:2.4rem;font-weight:900;color:{_g_col};'
                    f'      letter-spacing:-0.04em;line-height:1">{_g_met}/{_g_total}</span>'
                    f'  <span style="font-size:0.78rem;color:#64748B;font-weight:600;'
                    f'      text-transform:uppercase;letter-spacing:0.06em">targets hit</span>'
                    f'</div>'
                    f'<div style="height:5px;background:rgba(255,255,255,0.08);border-radius:3px;'
                    f'    overflow:hidden;margin-bottom:18px">'
                    f'  <div style="width:{_g_pct:.0f}%;height:100%;background:{_g_col};'
                    f'      border-radius:3px"></div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                # Per-channel, per-outcome rows — all in one HTML block for visual consistency
                _prog_html = ""
                _GSTEPS = [("calendar","meetings","Meetings"),
                           ("phone","calls","Calls"),
                           ("envelope","email","Email"),
                           ("link","linkedin","LinkedIn")]
                for icon_name, step, label in _GSTEPS:
                    ch_fields = [f for f in STEP_FIELDS[step] if f in _g_tgt_active]
                    if not ch_fields:
                        continue
                    _prog_html += (
                        f'<div style="font-size:0.65rem;font-weight:700;color:#475569;'
                        f'text-transform:uppercase;letter-spacing:0.09em;'
                        f'margin:14px 0 7px 0;display:flex;align-items:center;gap:5px">'
                        f'  {_svg(icon_name,11,"#475569")} {label}'
                        f'</div>'
                    )
                    for f in ch_fields:
                        t   = _g_tgt_active[f]
                        a   = _g_actual.get(f, 0)
                        pct = min(a / t * 100, 100) if t > 0 else 0
                        met = a >= t
                        val_col = "#10B981" if met else ("#E2E8F0" if a > 0 else "#475569")
                        bar_col = "#10B981" if met else ("#F59E0B" if a > 0 else "rgba(255,255,255,0.07)")
                        dot     = f'<span style="color:#10B981;font-size:0.65rem">●</span>' if met else ""
                        _prog_html += (
                            f'<div style="margin-bottom:10px">'
                            f'  <div style="display:flex;justify-content:space-between;'
                            f'      align-items:center;margin-bottom:4px">'
                            f'    <span style="font-size:0.78rem;color:#94A3B8">{FIELD_LABELS[f]}</span>'
                            f'    <span style="font-size:0.78rem;font-weight:700;color:{val_col};'
                            f'        white-space:nowrap;display:flex;align-items:center;gap:4px">'
                            f'      {dot}{a}'
                            f'      <span style="color:#334155;font-weight:400;font-size:0.73rem">'
                            f'        &thinsp;/&thinsp;{t}</span>'
                            f'    </span>'
                            f'  </div>'
                            f'  <div style="height:5px;background:rgba(255,255,255,0.07);'
                            f'      border-radius:3px;overflow:hidden">'
                            f'    <div style="width:{pct:.0f}%;height:100%;background:{bar_col};'
                            f'        border-radius:3px;transition:width .3s ease"></div>'
                            f'  </div>'
                            f'</div>'
                        )
                st.markdown(_prog_html, unsafe_allow_html=True)

                if not _g_row:
                    st.caption("No activity saved yet — log your week to update progress.")

    # ── Rep comparison for selected week ───────────────────────────────────────
    _rcomp = []
    for _rc_rep in get_setting("reps", []):
        _rc_tgt = _get_rep_targets(_rc_rep)
        _rc_fields = [f for f in COUNT_FIELDS if int(_rc_tgt.get(f, 0) or 0) > 0]
        if not _rc_fields:
            continue
        _rc_row    = get_existing_row(str(_g_wk), _rc_rep)
        _rc_actual = {f: int((_rc_row or {}).get(f, 0)) for f in COUNT_FIELDS}
        _rc_met    = sum(1 for f in _rc_fields if _rc_actual.get(f, 0) >= int(_rc_tgt[f]))
        _rc_pct    = _rc_met / len(_rc_fields) * 100
        _rcomp.append({"rep": _rc_rep, "met": _rc_met, "total": len(_rc_fields), "pct": _rc_pct})

    if _rcomp:
        _rcomp.sort(key=lambda x: x["pct"], reverse=True)
        st.markdown("")
        with st.container(border=True):
            st.markdown(
                f'<div class="card-hdr">'
                f'  <span class="card-hdr-icon">{_svg("user", 20, "#94A3B8")}</span>'
                f'  <div>'
                f'    <div class="card-hdr-title">Team Comparison</div>'
                f'    <div class="card-hdr-sub">Goal achievement this week — {_g_wk_lbl}</div>'
                f'  </div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            _medals = ["🥇", "🥈", "🥉"]
            _rc_html = ""
            for i, rc in enumerate(_rcomp):
                _col  = "#10B981" if rc["pct"] == 100 else ("#F59E0B" if rc["pct"] >= 50 else "#64748B")
                _rank = _medals[i] if i < 3 else f"{i+1}"
                _is_me = rc["rep"] == _g_rep
                _bg   = "rgba(185,28,28,0.08)" if _is_me else "transparent"
                _border = f"border-left:3px solid #B91C1C;" if _is_me else "border-left:3px solid transparent;"
                _rc_html += (
                    f'<div style="display:flex;align-items:center;gap:10px;'
                    f'padding:8px 6px;border-bottom:1px solid rgba(255,255,255,0.05);'
                    f'background:{_bg};{_border}">'
                    f'  <span style="font-size:1rem;width:22px;text-align:center">{_rank}</span>'
                    f'  <span style="font-size:0.82rem;font-weight:600;color:#E2E8F0;flex:1">'
                    f'    {rc["rep"]}</span>'
                    f'  <span style="font-size:0.78rem;color:#64748B;margin-right:8px">'
                    f'    {rc["met"]}/{rc["total"]}</span>'
                    f'  <div style="width:80px;height:5px;background:rgba(255,255,255,0.07);'
                    f'      border-radius:3px;overflow:hidden">'
                    f'    <div style="width:{rc["pct"]:.0f}%;height:100%;background:{_col};'
                    f'        border-radius:3px"></div>'
                    f'  </div>'
                    f'  <span style="font-size:0.78rem;font-weight:700;color:{_col};'
                    f'      width:36px;text-align:right">{rc["pct"]:.0f}%</span>'
                    f'</div>'
                )
            st.markdown(f'<div style="margin:-8px -12px">{_rc_html}</div>',
                        unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

with tab_dash:
    reps_list = get_setting("reps", [])
    today     = date.today()
    w, c      = get_weights(), {}

    # ── Filters ────────────────────────────────────────────────────────────────
    st.markdown('<div class="sec-label">Filters</div>', unsafe_allow_html=True)
    fc1, fc2, fc3 = st.columns(3)
    with fc1: f_start = st.date_input("From", value=today - timedelta(days=30), key="d_start")
    with fc2: f_end   = st.date_input("To",   value=today,                      key="d_end")
    with fc3: f_rep   = st.selectbox("Rep",   ["All"] + reps_list,              key="d_rep")

    filtered = get_daily_totals(f_start, f_end, f_rep)
    label    = f_rep if f_rep != "All" else "Team"

    # ── KPI cards ──────────────────────────────────────────────────────────────
    st.markdown(
        f'<div class="section-title">Key Metrics</div>'
        f'<div class="section-title-sub">{label} performance overview</div>',
        unsafe_allow_html=True,
    )
    kc1, kc2, kc3, kc4 = st.columns(4)
    kc1.metric(f"📅 Last Week — {label}",
               f"{sum_scores(get_daily_totals(week_start(today - timedelta(days=7)), week_start(today - timedelta(days=7)), f_rep), w, c)} pts")
    kc2.metric(f"📆 This Week — {label}",
               f"{sum_scores(get_daily_totals(week_start(), week_start(), f_rep), w, c)} pts")
    kc3.metric(f"🗓️ This Month — {label}",
               f"{sum_scores(get_daily_totals(month_start(), today, f_rep), w, c)} pts")
    kc4.metric(f"📊 Selected Period",
               f"{sum_scores(filtered, w, c)} pts")

    st.markdown("")

    # ── Leaderboard ────────────────────────────────────────────────────────────
    st.markdown(
        f'<div class="section-title">Leaderboard</div>'
        f'<div class="section-title-sub">{f_start} → {f_end}</div>',
        unsafe_allow_html=True,
    )
    lb_rows = get_leaderboard(filtered, reps_list, w, c)
    if lb_rows:
        _render_leaderboard(lb_rows, f_rep)
    else:
        st.info("No data for the selected period.")

    st.markdown("")

    # ── Per-rep channel breakdown table ───────────────────────────────────────
    st.markdown(
        '<div class="section-title">Channel Breakdown</div>'
        '<div class="section-title-sub">Points by rep and channel for the selected period</div>',
        unsafe_allow_html=True,
    )
    if filtered:
        chs    = get_channels()
        br_data = []
        for row in filtered:
            s     = compute_row_score(row, w, c)
            entry = {"Rep": row["rep_name"]}
            entry.update({ch: round(s["channel_totals"].get(ch, 0), 1) for ch in chs})
            br_data.append(entry)
        br_df = pd.DataFrame(br_data).groupby("Rep")[chs].sum().reset_index()
        br_df["Total"] = br_df[chs].sum(axis=1).round(1)
        st.dataframe(br_df, use_container_width=True, hide_index=True)
    else:
        st.info("No data.")

    st.markdown("")

    # ── Charts ─────────────────────────────────────────────────────────────────
    st.markdown(
        '<div class="section-title">Charts</div>'
        '<div class="section-title-sub">Score trend and channel distribution for the selected period</div>',
        unsafe_allow_html=True,
    )
    ch_col1, ch_col2 = st.columns(2, gap="large")

    with ch_col1:
        with st.container(border=True):
            st.markdown(
                '<div class="chart-title">Score Trend</div>'
                '<div class="chart-sub">Last 30 days</div>',
                unsafe_allow_html=True,
            )
            trend_start = today - timedelta(days=29)
            t_rows      = get_daily_totals(trend_start, today, f_rep)
            date_range  = pd.date_range(start=trend_start, end=today, freq="D")

            if t_rows:
                tdata = [{"Date": pd.Timestamp(r["date"]),
                           "Rep": r["rep_name"],
                           "Score": compute_row_total(r, w, c)} for r in t_rows]
                tdf   = pd.DataFrame(tdata)
                if f_rep == "All":
                    active = tdf["Rep"].unique().tolist()
                    grid   = pd.DataFrame({"Date": date_range}).merge(
                        pd.DataFrame({"Rep": active}), how="cross")
                    grp    = tdf.groupby(["Date", "Rep"])["Score"].sum().reset_index()
                    merged = grid.merge(grp, on=["Date", "Rep"], how="left").fillna(0)
                    fig    = px.line(merged, x="Date", y="Score", color="Rep",
                                     labels={"Score": "Points"},
                                     color_discrete_sequence=CHART_COLORS)
                else:
                    daily = (tdf.groupby("Date")["Score"].sum()
                             .reindex(date_range, fill_value=0).reset_index())
                    daily.columns = ["Date", "Score"]
                    fig = px.area(daily, x="Date", y="Score",
                                   labels={"Score": "Points"},
                                   color_discrete_sequence=[BRAND_RED])
                    fig.update_traces(fillcolor="rgba(185,28,28,0.15)", line_color=BRAND_RED)
            else:
                empty = pd.DataFrame({"Date": date_range, "Score": 0.0})
                fig   = px.area(empty, x="Date", y="Score",
                                 color_discrete_sequence=[BRAND_RED])
                fig.update_traces(fillcolor="rgba(185,28,28,0.08)")

            st.plotly_chart(_apply_chart_style(fig), use_container_width=True)

    with ch_col2:
        with st.container(border=True):
            st.markdown(
                '<div class="chart-title">Points by Channel</div>'
                '<div class="chart-sub">Distribution across outreach types</div>',
                unsafe_allow_html=True,
            )
            if filtered:
                chs    = get_channels()
                ch_data = []
                for row in filtered:
                    s = compute_row_score(row, w, c)
                    for ch, pts in s["channel_totals"].items():
                        ch_data.append({"Channel": ch, "Rep": row["rep_name"], "Points": pts})
                cdf = pd.DataFrame(ch_data)
                if f_rep == "All":
                    g2   = cdf.groupby(["Channel", "Rep"])["Points"].sum().reset_index()
                    fig2 = px.bar(g2, x="Channel", y="Points", color="Rep",
                                   barmode="group", color_discrete_sequence=CHART_COLORS)
                else:
                    g2   = cdf.groupby("Channel")["Points"].sum().reset_index()
                    fig2 = px.bar(g2, x="Channel", y="Points", color="Channel",
                                   color_discrete_sequence=CHART_COLORS)
                fig2.update_traces(marker_line_width=0)
                st.plotly_chart(_apply_chart_style(fig2), use_container_width=True)
            else:
                st.info("No data for the selected period.")

    st.markdown("")

    # ── Goal achievement history ────────────────────────────────────────────────
    _ga_data = []
    for row in filtered:
        _r_rep = row["rep_name"]
        _r_tgt = _get_rep_targets(_r_rep)
        _r_tgt_fields = [f for f in COUNT_FIELDS if int(_r_tgt.get(f, 0) or 0) > 0]
        if not _r_tgt_fields:
            continue
        _r_met = sum(1 for f in _r_tgt_fields if row.get(f, 0) >= int(_r_tgt[f]))
        _ga_data.append({
            "Date": pd.Timestamp(row["date"]),
            "Rep":  _r_rep,
            "Goals Hit %": round(_r_met / len(_r_tgt_fields) * 100, 1),
        })

    if _ga_data:
        st.markdown(
            '<div class="section-title">Goal Achievement</div>'
            '<div class="section-title-sub">% of weekly targets hit per rep over time</div>',
            unsafe_allow_html=True,
        )
        with st.container(border=True):
            st.markdown(
                '<div class="chart-title">Target Achievement History</div>'
                '<div class="chart-sub">100% = all targets met · dashed lines at 100% and 80%</div>',
                unsafe_allow_html=True,
            )
            _ga_df = pd.DataFrame(_ga_data)
            if f_rep == "All":
                _ga_fig = px.line(_ga_df, x="Date", y="Goals Hit %", color="Rep",
                                  range_y=[0, 110], markers=True,
                                  color_discrete_sequence=CHART_COLORS)
            else:
                _ga_fig = px.area(_ga_df, x="Date", y="Goals Hit %",
                                  range_y=[0, 110], markers=True,
                                  color_discrete_sequence=[BRAND_RED])
                _ga_fig.update_traces(fillcolor="rgba(185,28,28,0.12)", line_color=BRAND_RED)
            _ga_fig.add_hline(y=100, line_dash="dot", line_color="#10B981",
                              line_width=1, opacity=0.5,
                              annotation_text="100%", annotation_font_color="#10B981",
                              annotation_font_size=10)
            _ga_fig.add_hline(y=80, line_dash="dot", line_color="#F59E0B",
                              line_width=1, opacity=0.4,
                              annotation_text="80%", annotation_font_color="#F59E0B",
                              annotation_font_size=10)
            st.plotly_chart(_apply_chart_style(_ga_fig, height=260),
                            use_container_width=True)

    st.markdown("")

    # ── Daily totals table ─────────────────────────────────────────────────────
    st.markdown(
        '<div class="section-title">Activity Log</div>'
        '<div class="section-title-sub">Full weekly record for the selected period</div>',
        unsafe_allow_html=True,
    )
    if filtered:
        chs        = get_channels()
        table_rows = []
        for row in filtered:
            s = compute_row_score(row, w, c)
            table_rows.append({
                "ID":      row["id"],
                "Date":    row["date"],
                "Rep":     row["rep_name"],
                "Score":   s["total"],
                "Quality": f"{s['quality_ratio']:.0%}",
                **{ch: round(s["channel_totals"].get(ch, 0), 1) for ch in chs},
                "Notes":   row.get("notes", ""),
            })
        st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)

        with st.expander("🗑️ Delete a row"):
            id_map = {
                f"#{r['id']}  {r['date']}  |  {r['rep_name']}  |  "
                f"{compute_row_total(r, w, c)} pts": r["id"]
                for r in filtered
            }
            chosen = st.selectbox("Select row to delete", list(id_map.keys()), key="del_sel")
            if st.button("Confirm Delete", type="secondary", key="del_btn"):
                delete_daily_total(id_map[chosen])
                st.success("Deleted."); st.rerun()
    else:
        st.info("No data for the selected period.")

    st.markdown("")

    # ── Export ─────────────────────────────────────────────────────────────────
    st.markdown('<div class="sec-label">Export Data</div>', unsafe_allow_html=True)
    ex1, ex2 = st.columns(2)
    with ex1:
        if filtered:
            raw = pd.DataFrame([
                {"date": r["date"], "rep_name": r["rep_name"],
                 **{f: r.get(f, 0) for f in COUNT_FIELDS}, "notes": r.get("notes", "")}
                for r in filtered
            ]).to_csv(index=False)
            st.download_button("📥 Raw Weekly Totals (CSV)", data=raw,
                               file_name=f"weekly_totals_{f_start}_{f_end}.csv",
                               mime="text/csv", use_container_width=True)
        else:
            st.button("📥 Raw Weekly Totals (CSV)", disabled=True, use_container_width=True)

    with ex2:
        if filtered:
            st.download_button("📥 Summary Report (CSV)",
                               data=create_summary_csv(filtered, reps_list),
                               file_name=f"summary_{f_start}_{f_end}.csv",
                               mime="text/csv", use_container_width=True)
        else:
            st.button("📥 Summary Report (CSV)", disabled=True, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — IMPORT CSV
# ══════════════════════════════════════════════════════════════════════════════

with tab_import:
    st.markdown('<div class="sec-label">Import CSV</div>', unsafe_allow_html=True)

    CSV_COLS = ["date", "rep_name"] + COUNT_FIELDS + ["notes"]

    ic1, ic2 = st.columns([3, 2], gap="large")

    with ic1:
        with st.container(border=True):
            st.markdown("##### How it works")
            st.markdown(
                '<div class="import-info">'
                'Each CSV row represents <strong>one rep for one week</strong> (use the week-start Monday as the date).<br>'
                'All activity count columns must be present (or will be filled with 0).<br>'
                'Rows violating funnel order (e.g. Connects &gt; Dials) are '
                '<strong>rejected</strong> — reasons shown in the summary.<br>'
                'Existing rows for the same (date, rep) are <strong>overwritten</strong> by default.'
                '</div>',
                unsafe_allow_html=True,
            )
            add_import = st.checkbox("➕  Add to existing rows instead of overwriting",
                                     key="import_add_to")

            template_row = {"date": date.today().isoformat(), "rep_name": "Alice Johnson",
                            "notes": ""}
            template_row.update({f: 0 for f in COUNT_FIELDS})
            tpl_csv = pd.DataFrame([template_row])[CSV_COLS].to_csv(index=False)
            st.download_button("📋 Download CSV Template", data=tpl_csv,
                               file_name="import_template.csv", mime="text/csv",
                               use_container_width=True)

    with ic2:
        with st.container(border=True):
            st.markdown("##### Upload File")
            uploaded_csv = st.file_uploader("Choose CSV", type=["csv"], key="import_csv",
                                            label_visibility="collapsed")

    if uploaded_csv:
        try:
            df = pd.read_csv(uploaded_csv)
        except Exception as e:
            st.error(f"Could not parse CSV: {e}"); df = None

        if df is not None:
            missing = {"date", "rep_name"} - set(df.columns)
            if missing:
                st.error(f"Missing required columns: {missing}")
            else:
                for f in COUNT_FIELDS:
                    if f not in df.columns: df[f] = 0
                if "notes" not in df.columns: df["notes"] = ""
                try:
                    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
                except Exception:
                    st.error("Could not parse 'date' column — use YYYY-MM-DD."); df = None

            if df is not None:
                errs = []
                for f in COUNT_FIELDS:
                    try:
                        df[f] = pd.to_numeric(df[f], errors="coerce").fillna(0).astype(int)
                    except Exception:
                        errs.append(f)
                if errs:
                    st.error(f"Non-numeric values in: {errs}")
                else:
                    # ── Funnel validation per row ───────────────────────────────
                    bad_rows, good_indices = [], []
                    for idx, row in df.iterrows():
                        counts_r = {f: int(row.get(f, 0)) for f in COUNT_FIELDS}
                        row_errs = [
                            e
                            for step_errs in validate_all(counts_r).values()
                            for e in step_errs
                        ]
                        if row_errs:
                            bad_rows.append({
                                "Row #":     idx + 2,
                                "Date":      row["date"],
                                "Rep":       row["rep_name"],
                                "Violation": " | ".join(row_errs),
                            })
                        else:
                            good_indices.append(idx)

                    good_df = df.loc[good_indices].reset_index(drop=True)

                    if bad_rows:
                        st.warning(
                            f"⚠️  {len(bad_rows)} row(s) rejected — funnel constraints violated:"
                        )
                        st.dataframe(pd.DataFrame(bad_rows), use_container_width=True,
                                     hide_index=True)

                    if good_df.empty:
                        st.error("No valid rows to import after funnel validation.")
                    else:
                        st.success(
                            f"✅  {len(good_df)} valid row(s) ready to import"
                            + (f"  ·  {len(bad_rows)} rejected" if bad_rows else "")
                        )
                        st.dataframe(good_df[CSV_COLS].head(20), use_container_width=True,
                                     hide_index=True)
                        if st.button("📥 Import into Database", type="primary",
                                     key="do_import", use_container_width=True):
                            imported, failed = 0, []
                            for i_row, row in good_df.iterrows():
                                try:
                                    upsert_daily_total(
                                        str(row["date"]), str(row["rep_name"]),
                                        {f: int(row.get(f, 0)) for f in COUNT_FIELDS},
                                        str(row.get("notes", "") or ""), add_import,
                                    )
                                    imported += 1
                                except Exception as e:
                                    failed.append(f"Row {i_row + 2}: {e}")
                            st.success(f"✅  Imported {imported} row(s).")
                            if failed:
                                st.warning(f"{len(failed)} row(s) failed:")
                                for msg in failed[:10]: st.caption(msg)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — SETTINGS
# ══════════════════════════════════════════════════════════════════════════════

with tab_settings:
    st.markdown('<div class="sec-label">Configuration</div>', unsafe_allow_html=True)

    s_col1, s_col2, s_col3 = st.columns([2, 3, 2], gap="large")

    with s_col1:
        with st.container(border=True):
            st.markdown("##### 👥 Sales Reps")
            st.caption("One name per line.")
            cur_reps   = get_setting("reps", [])
            reps_input = st.text_area("Reps", "\n".join(cur_reps),
                                      height=130, key="s_reps",
                                      label_visibility="collapsed")

        with st.container(border=True):
            st.markdown("##### 📅 Week Start")
            ws_mon   = get_setting("week_starts_monday", True)
            week_opt = st.radio("First day", ["Monday", "Sunday"],
                                index=0 if ws_mon else 1,
                                horizontal=True, key="s_week")

    with s_col2:
        with st.container(border=True):
            st.markdown("##### 🎯 Scoring Weights")
            st.caption('`{ "Channel": { "Outcome": points } }`')
            weights_input = st.text_area(
                "Weights", json.dumps(get_setting("weights", {}), indent=2),
                height=380, key="s_weights", label_visibility="collapsed",
            )

    with s_col3:
        with st.container(border=True):
            st.markdown("##### 📋 Scoring Cheat-Sheet")
            ws = get_weights()
            cs_rows = []
            for ch, outcomes in ws.items():
                for outcome, pts in outcomes.items():
                    cs_rows.append({"Ch": ch, "Outcome": outcome, "Pts": pts})
            st.dataframe(pd.DataFrame(cs_rows), use_container_width=True,
                         hide_index=True, height=220)

    st.markdown("")

    if st.button("💾 Save Settings", type="primary", use_container_width=True, key="save_s"):
        errs  = []
        new_w = None

        new_reps = [r.strip() for r in reps_input.splitlines() if r.strip()]
        if not new_reps:
            errs.append("Rep list cannot be empty.")
        try:
            new_w = json.loads(weights_input)
            if not isinstance(new_w, dict): errs.append("Weights must be a JSON object.")
        except json.JSONDecodeError as e:
            errs.append(f"Weights JSON error: {e}")

        if errs:
            for e in errs: st.error(e)
        else:
            set_setting("reps",               new_reps)
            set_setting("weights",            new_w)
            set_setting("week_starts_monday", week_opt == "Monday")
            st.success("✅  Settings saved!")
            st.rerun()

    st.markdown("")
    with st.expander("🔍 Debug: Draft State", expanded=False):
        st.write(f"**Current step:** {st.session_state.get('wizard_step', 0)}")
        _dbg_draft = st.session_state.get("_draft", {})
        st.write("**_draft (authoritative):**")
        st.json({f: _dbg_draft.get(f, 0) for f in COUNT_FIELDS})
        _dbg_total = compute_row_total({f: int(_dbg_draft.get(f, 0) or 0) for f in COUNT_FIELDS}, get_weights(), {})
        st.metric("Computed Score (_draft)", _dbg_total)

    st.markdown("")
    st.markdown('<div class="sec-label">Data Management</div>', unsafe_allow_html=True)
    st.caption("View and remove uploaded entries by rep. Use this to fix mistakes like entries saved under the wrong name.")

    _all_rows = get_daily_totals()
    _w_dm = get_weights()
    _c_dm = {}

    if not _all_rows:
        st.info("No data in the database yet.")
    else:
        # Group rows by rep
        _rep_rows: dict = {}
        for _r in _all_rows:
            _rep_rows.setdefault(_r["rep_name"], []).append(_r)

        for _rep, _rows in sorted(_rep_rows.items()):
            _total_pts = sum(compute_row_total(_r, _w_dm, _c_dm) for _r in _rows)
            with st.expander(f"**{_rep}** — {len(_rows)} entr{'y' if len(_rows)==1 else 'ies'}  ·  {_total_pts} pts total"):
                # Table of entries
                _entry_rows = []
                for _r in sorted(_rows, key=lambda x: x["date"], reverse=True):
                    _pts = compute_row_total(_r, _w_dm, _c_dm)
                    _entry_rows.append({
                        "ID":    _r["id"],
                        "Week":  _r["date"],
                        "Score": _pts,
                        "Notes": _r.get("notes", ""),
                    })
                st.dataframe(pd.DataFrame(_entry_rows), use_container_width=True, hide_index=True)

                st.markdown("")
                _dm_col1, _dm_col2 = st.columns([3, 1])
                with _dm_col1:
                    st.warning(
                        f"⚠️ This will permanently delete **all {len(_rows)} entr{'y' if len(_rows)==1 else 'ies'}** "
                        f"for **{_rep}**. This cannot be undone."
                    )
                with _dm_col2:
                    if st.button(
                        f"🗑️ Remove all",
                        key=f"dm_del_{_rep}",
                        type="secondary",
                        use_container_width=True,
                    ):
                        _deleted = delete_rep_totals(_rep)
                        st.success(f"Deleted {_deleted} entr{'y' if _deleted==1 else 'ies'} for {_rep}.")
                        st.rerun()
