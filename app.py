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
    get_caps,
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
    "li_convo_started":      "2+ back-and-forth exchanges establishing rapport or uncovering need.",
    "li_meeting_booked":     "A meeting booked as a direct result of your LinkedIn outreach.",
}

CHART_COLORS = px.colors.qualitative.Set2
BRAND_RED    = "#B91C1C"
BRAND_GREEN  = "#10B981"
BRAND_AMBER  = "#F59E0B"


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
    When rep or date changes, pull that day's saved record into the count
    fields. If no record exists the fields are left as-is (initialised to 0
    by _init_session on first load; only Clear Draft resets them).
    """
    rep  = st.session_state.get("draft_rep", "")
    dval = str(st.session_state.get("draft_date", date.today()))
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
    c = caps    or get_caps()
    return round(sum(compute_row_total(r, w, c) for r in rows), 1)


def create_summary_csv(rows: list, reps: list) -> str:
    if not rows:
        return ""
    w, c = get_weights(), get_caps()
    buf  = io.StringIO()

    buf.write("LEADERBOARD\n")
    lb = pd.DataFrame(get_leaderboard(rows, reps, w, c)).drop(columns=["_qr"], errors="ignore")
    lb.to_csv(buf, index=False)

    buf.write("\nDAILY TOTALS WITH SCORE\n")
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


def _copy_yesterday() -> bool:
    rep = st.session_state.get("draft_rep", "")
    if not rep:
        return False
    row = get_existing_row(str(date.today() - timedelta(days=1)), rep)
    if not row:
        return False
    for f in COUNT_FIELDS:
        val = row.get(f, 0)
        st.session_state[f] = val
        st.session_state["_draft"][f] = val
    return True


def _load_typical() -> int:
    """Fill counts with the 7-day rolling average for the selected rep."""
    rep = st.session_state.get("draft_rep", "")
    if not rep:
        return 0
    rows = get_daily_totals(date.today() - timedelta(days=7),
                            date.today() - timedelta(days=1), rep)
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
    cs  = get_caps()
    wt  = wts.get(channel, {}).get(outcome, 0)
    cap = cs.get(channel, {}).get(outcome)
    cap_str  = f"  ·  Cap: {cap}/day" if cap else "  ·  Uncapped"
    desc     = OUTCOME_HELP.get(field, "")
    help_txt = f"**{wt} pts each**{cap_str}\n\n{desc}"
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
    """Right-side live scoring summary — updates on every widget change."""
    _d = st.session_state.get("_draft", {})
    counts = {f: int(_d.get(f, 0) or 0) for f in COUNT_FIELDS}
    w, c   = get_weights(), get_caps()
    s      = compute_row_score(counts, w, c)
    total  = s["total"]
    qr     = s["quality_ratio"]
    chs    = get_channels()

    with st.container(border=True):
        # Total score
        st.markdown(
            f'<div class="lsp-total-sub">Live Score</div>'
            f'<div class="lsp-total">{total}</div>'
            f'<div class="lsp-total-sub" style="margin-top:2px">points</div>',
            unsafe_allow_html=True,
        )
        # Quality ratio progress bar
        st.markdown(
            f'<div class="lsp-prog-track">'
            f'  <div class="lsp-prog-fill" style="width:{min(qr * 100, 100):.0f}%"></div>'
            f'</div>'
            f'<div class="lsp-qr-badge">{qr:.0%} quality</div>',
            unsafe_allow_html=True,
        )
        # Channel breakdown — mini progress bars
        st.markdown('<div class="lsp-sec">By Channel</div>', unsafe_allow_html=True)
        ch_totals = s["channel_totals"]
        max_ch    = max(ch_totals.values(), default=1) or 1
        bars_html = ""
        any_pts   = False
        for ch in chs:
            pts = ch_totals.get(ch, 0)
            pct = min(pts / max_ch * 100, 100) if max_ch > 0 else 0
            ico = CHANNEL_ICONS.get(ch, "•")
            if pts > 0:
                any_pts = True
            bars_html += (
                f'<div class="ch-bar-wrap">'
                f'  <span class="ch-bar-label">{ico} {ch}</span>'
                f'  <div class="ch-bar-track">'
                f'    <div class="ch-bar-fill" style="width:{pct:.0f}%"></div>'
                f'  </div>'
                f'  <span class="ch-bar-pts">{pts:.0f}</span>'
                f'</div>'
            )
        if any_pts:
            st.markdown(f'<div>{bars_html}</div>', unsafe_allow_html=True)
        else:
            st.markdown(bars_html, unsafe_allow_html=True)  # show empty bars
        # Cap warnings
        if s["cap_warnings"]:
            st.markdown('<div class="lsp-sec">Cap Warnings</div>', unsafe_allow_html=True)
            for w_str in s["cap_warnings"]:
                st.markdown(f'<div class="lsp-cap-warn">⚠️ {w_str}</div>',
                            unsafe_allow_html=True)
        # Step completion status
        st.markdown('<div class="lsp-sec">Steps filled</div>', unsafe_allow_html=True)
        icons_html = ""
        for i, ico in enumerate(STEP_ICONS[:4]):
            filled = any(_d.get(f, 0) > 0
                         for f in STEP_FIELDS[STEP_NAMES[i]])
            color  = BRAND_GREEN if filled else "rgba(255,255,255,0.18)"
            icons_html += f'<span style="color:{color}">{ico}</span>'
        st.markdown(f'<div class="lsp-step-icons">{icons_html}</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# Wizard — step renderers
# ══════════════════════════════════════════════════════════════════════════════

def _step_meetings() -> None:
    _card_header("📅", "Meetings", "How many meetings did you hold today?")
    with st.form("step_meetings_form"):
        c1, _ = st.columns(2)
        _count_input("meeting_held", col=c1)
        st.markdown("")
        _, nav_r = st.columns(2)
        with nav_r:
            next_sub = st.form_submit_button("Next →", type="primary", use_container_width=True)
    _proof_section("meetings")
    if next_sub:
        st.session_state["_draft"]["meeting_held"] = int(st.session_state.get("meeting_held", 0) or 0)
        st.session_state["_step_errors"] = []
        st.session_state["_error_step"] = ""
        st.session_state.wizard_step += 1
        st.rerun()


def _step_calls() -> None:
    _card_header("📞", "Calls", "Log every call attempt and outcome from your session today.")
    _errors = st.session_state.get("_step_errors", []) if st.session_state.get("_error_step") == "calls" else []
    with st.form("step_calls_form"):
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
            autofix_sub = st.form_submit_button("🔧 Auto-fix Calls", type="secondary", use_container_width=True)
        else:
            autofix_sub = False
        nav_l, nav_r = st.columns(2)
        with nav_l:
            prev_sub = st.form_submit_button("← Previous", use_container_width=True)
        with nav_r:
            next_sub = st.form_submit_button("Next →", type="primary", use_container_width=True)
    _proof_section("calls")
    if autofix_sub:
        _c = {f: int(st.session_state.get(f, 0) or 0) for f in STEP_FIELDS["calls"]}
        for f, v in autofix_step("calls", _c).items():
            st.session_state[f] = v
            st.session_state["_draft"][f] = v
        st.session_state["_step_errors"] = []
        st.session_state["_error_step"] = ""
        st.rerun()
    elif prev_sub:
        for f in STEP_FIELDS["calls"]:
            st.session_state["_draft"][f] = int(st.session_state.get(f, 0) or 0)
        st.session_state["_step_errors"] = []
        st.session_state["_error_step"] = ""
        st.session_state.wizard_step -= 1
        st.rerun()
    elif next_sub:
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
    _card_header("✉️", "Email", "Count every outbound email and any replies you received today.")
    _errors = st.session_state.get("_step_errors", []) if st.session_state.get("_error_step") == "email" else []
    with st.form("step_email_form"):
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
            autofix_sub = st.form_submit_button("🔧 Auto-fix Email", type="secondary", use_container_width=True)
        else:
            autofix_sub = False
        nav_l, nav_r = st.columns(2)
        with nav_l:
            prev_sub = st.form_submit_button("← Previous", use_container_width=True)
        with nav_r:
            next_sub = st.form_submit_button("Next →", type="primary", use_container_width=True)
    _proof_section("email")
    if autofix_sub:
        _c = {f: int(st.session_state.get(f, 0) or 0) for f in STEP_FIELDS["email"]}
        for f, v in autofix_step("email", _c).items():
            st.session_state[f] = v
            st.session_state["_draft"][f] = v
        st.session_state["_step_errors"] = []
        st.session_state["_error_step"] = ""
        st.rerun()
    elif prev_sub:
        for f in STEP_FIELDS["email"]:
            st.session_state["_draft"][f] = int(st.session_state.get(f, 0) or 0)
        st.session_state["_step_errors"] = []
        st.session_state["_error_step"] = ""
        st.session_state.wizard_step -= 1
        st.rerun()
    elif next_sub:
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
    _card_header("🔗", "LinkedIn", "Record all LinkedIn outreach activity from today.")
    _errors = st.session_state.get("_step_errors", []) if st.session_state.get("_error_step") == "linkedin" else []
    with st.form("step_linkedin_form"):
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
            autofix_sub = st.form_submit_button("🔧 Auto-fix LinkedIn", type="secondary", use_container_width=True)
        else:
            autofix_sub = False
        nav_l, nav_r = st.columns(2)
        with nav_l:
            prev_sub = st.form_submit_button("← Previous", use_container_width=True)
        with nav_r:
            next_sub = st.form_submit_button("Review & Save →", type="primary", use_container_width=True)
    _proof_section("linkedin")
    if autofix_sub:
        _c = {f: int(st.session_state.get(f, 0) or 0) for f in STEP_FIELDS["linkedin"]}
        for f, v in autofix_step("linkedin", _c).items():
            st.session_state[f] = v
            st.session_state["_draft"][f] = v
        st.session_state["_step_errors"] = []
        st.session_state["_error_step"] = ""
        st.rerun()
    elif prev_sub:
        for f in STEP_FIELDS["linkedin"]:
            st.session_state["_draft"][f] = int(st.session_state.get(f, 0) or 0)
        st.session_state["_step_errors"] = []
        st.session_state["_error_step"] = ""
        st.session_state.wizard_step -= 1
        st.rerun()
    elif next_sub:
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
    date_val = str(st.session_state.get("draft_date", date.today()))
    rep_name = st.session_state.get("draft_rep", "")
    _d       = st.session_state.get("_draft", {})
    counts   = {f: int(_d.get(f, 0) or 0) for f in COUNT_FIELDS}
    w, c     = get_weights(), get_caps()
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
        f'      {rep_name or "<em>No rep selected</em>"}&nbsp;·&nbsp;{date_val}'
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

    # ── Cap warnings ───────────────────────────────────────────────────────────
    for warn in scored["cap_warnings"]:
        st.warning(f"⚠️  Cap applied: {warn}")

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
    st.text_area("Day notes (optional)", key="draft_notes", height=75)

    existing = get_existing_row(date_val, rep_name)
    add_to   = False
    if existing:
        st.info(
            f"📝 Updating existing record for **{rep_name}** on **{date_val}**. "
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
        if st.button("💾 Save Day", type="primary", use_container_width=True, key="rev_save",
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
                st.success(f"✅  {action}! **{rep_name}** on **{date_val}** — "
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
        '    <div class="sb-logo-sub">Daily Activity Log</div>'
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

    # ── Date picker ────────────────────────────────────────────────────────────
    st.markdown('<div class="sb-section">Date</div>', unsafe_allow_html=True)
    st.date_input("Date", key="draft_date", value=date.today(), label_visibility="collapsed")

    # ── This-week day buttons ──────────────────────────────────────────────────
    st.markdown('<div class="sb-section">This Week</div>', unsafe_allow_html=True)
    _today     = date.today()
    _wk_start  = week_start(_today)
    _wk_days   = [_wk_start + timedelta(days=i) for i in range(5)]  # Mon–Fri
    _sel_date  = st.session_state.get("draft_date", _today)
    _day_lbls  = ["M", "T", "W", "T", "F"]
    _day_cols  = st.columns(5)
    for _i, (_dc, _wd) in enumerate(zip(_day_cols, _wk_days)):
        _is_sel = (_wd == _sel_date)
        _is_tod = (_wd == _today)
        _tip    = _wd.strftime("%A %d %b") + (" · today" if _is_tod else "")
        with _dc:
            if st.button(
                _day_lbls[_i],
                key=f"wkday_{_i}",
                type="primary" if _is_sel else "secondary",
                use_container_width=True,
                help=_tip,
            ):
                st.session_state["draft_date"]  = _wd
                st.session_state["_loaded_for"] = None  # force reload for new date
                st.rerun()

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

    # ── Quick actions ──────────────────────────────────────────────────────────
    st.markdown('<div class="sb-section">Quick Actions</div>', unsafe_allow_html=True)

    if st.button("⬛  Zero All Fields", use_container_width=True, key="sb_zero"):
        _zero_all(); st.rerun()

    if st.button("📋  Copy Yesterday", use_container_width=True, key="sb_copy"):
        if _copy_yesterday():
            st.toast("Copied from yesterday!", icon="✅")
        else:
            st.toast("No record found for yesterday.", icon="⚠️")
        st.rerun()

    if st.button("📈  Typical Day (7-day avg)", use_container_width=True, key="sb_typical"):
        n = _load_typical()
        if n:
            st.toast(f"Loaded average of {n} day(s)", icon="📈")
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

_h_rep  = st.session_state.get("draft_rep", "")
_h_date = str(st.session_state.get("draft_date", date.today()))
_h_meta = (
    f"<strong>{_h_rep}</strong>&nbsp;·&nbsp;{_h_date}"
    if _h_rep else _h_date
)
st.markdown(
    f'<div class="app-hero">'
    f'  <div class="app-hero-eyebrow">RWS · Daily Activity Tracker</div>'
    f'  <div class="app-hero-title">Sales Command Centre</div>'
    f'  <div class="app-hero-meta">{_h_meta}</div>'
    f'</div>',
    unsafe_allow_html=True,
)


# ══════════════════════════════════════════════════════════════════════════════
# Main tabs
# ══════════════════════════════════════════════════════════════════════════════

tab_wizard, tab_dash, tab_import, tab_settings = st.tabs(
    ["📝  Daily Log", "📈  Dashboard", "📤  Import CSV", "⚙️  Settings"]
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
# TAB 2 — DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

with tab_dash:
    reps_list = get_setting("reps", [])
    today     = date.today()
    w, c      = get_weights(), get_caps()

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
    kc1.metric(f"📅 Today — {label}",
               f"{sum_scores(get_daily_totals(today, today, f_rep), w, c)} pts")
    kc2.metric(f"📆 This Week — {label}",
               f"{sum_scores(get_daily_totals(week_start(), today, f_rep), w, c)} pts")
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
                '<div class="chart-title">Daily Score Trend</div>'
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

    # ── Daily totals table ─────────────────────────────────────────────────────
    st.markdown(
        '<div class="section-title">Activity Log</div>'
        '<div class="section-title-sub">Full daily record for the selected period</div>',
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
            st.download_button("📥 Raw Daily Totals (CSV)", data=raw,
                               file_name=f"daily_totals_{f_start}_{f_end}.csv",
                               mime="text/csv", use_container_width=True)
        else:
            st.button("📥 Raw Daily Totals (CSV)", disabled=True, use_container_width=True)

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
                'Each CSV row represents <strong>one rep on one date</strong>.<br>'
                'All 15 activity count columns must be present (or will be filled with 0).<br>'
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
            st.markdown("##### 🚦 Daily Caps")
            st.caption("Capped per rep per day. Omitted outcomes = uncapped.")
            caps_input = st.text_area(
                "Caps", json.dumps(get_setting("caps", {}), indent=2),
                height=180, key="s_caps", label_visibility="collapsed",
            )

        with st.container(border=True):
            st.markdown("##### 📋 Scoring Cheat-Sheet")
            ws = get_weights(); cs = get_caps()
            cs_rows = []
            for ch, outcomes in ws.items():
                for outcome, pts in outcomes.items():
                    cap_v = cs.get(ch, {}).get(outcome)
                    cs_rows.append({
                        "Ch": ch, "Outcome": outcome, "Pts": pts,
                        "Cap": f"{cap_v}/d" if cap_v else "—",
                    })
            st.dataframe(pd.DataFrame(cs_rows), use_container_width=True,
                         hide_index=True, height=220)

    st.markdown("")

    if st.button("💾 Save Settings", type="primary", use_container_width=True, key="save_s"):
        errs  = []
        new_w = None
        new_c = None

        new_reps = [r.strip() for r in reps_input.splitlines() if r.strip()]
        if not new_reps:
            errs.append("Rep list cannot be empty.")
        try:
            new_w = json.loads(weights_input)
            if not isinstance(new_w, dict): errs.append("Weights must be a JSON object.")
        except json.JSONDecodeError as e:
            errs.append(f"Weights JSON error: {e}")
        try:
            new_c = json.loads(caps_input)
            if not isinstance(new_c, dict): errs.append("Caps must be a JSON object.")
        except json.JSONDecodeError as e:
            errs.append(f"Caps JSON error: {e}")

        if errs:
            for e in errs: st.error(e)
        else:
            set_setting("reps",               new_reps)
            set_setting("weights",            new_w)
            set_setting("caps",               new_c)
            set_setting("week_starts_monday", week_opt == "Monday")
            st.success("✅  Settings saved!")
            st.rerun()

    st.markdown("")
    with st.expander("🔍 Debug: Draft State", expanded=False):
        st.write(f"**Current step:** {st.session_state.get('wizard_step', 0)}")
        _dbg_draft = st.session_state.get("_draft", {})
        st.write("**_draft (authoritative):**")
        st.json({f: _dbg_draft.get(f, 0) for f in COUNT_FIELDS})
        _dbg_total = compute_row_total({f: int(_dbg_draft.get(f, 0) or 0) for f in COUNT_FIELDS}, get_weights(), get_caps())
        st.metric("Computed Score (_draft)", _dbg_total)
