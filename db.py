"""
db.py — SQLite persistence for the Daily Sales Activity Tracker.
"""

import json
import os
import sqlite3
from datetime import datetime

# When deployed (Railway), set DATA_DIR=/data (mounted persistent volume).
# Locally defaults to the current working directory.
DB_PATH = os.path.join(os.environ.get("DATA_DIR", "."), "sales_tracker.db")

# Increment this whenever DEFAULT_SETTINGS["weights"] changes.
# init_db() uses it to re-apply new weights to existing databases automatically.
WEIGHTS_VERSION = 4

# ── Canonical list of all count columns (order defines DB schema) ──────────────
COUNT_FIELDS = [
    # Meetings
    "meeting_held",
    # Calls
    "call_dial", "call_connect", "call_meaningful_convo", "call_meeting_booked",
    # Email
    "email_sent", "email_reply", "email_positive", "email_meeting_booked",
    # LinkedIn
    "li_request_sent", "li_accepted", "li_reply", "li_meeting_booked",
]

DEFAULT_SETTINGS = {
    "reps": ["Alice Johnson", "Bob Smith", "Carol White", "David Brown"],
    # ── Quality-driven weights (v3) ──────────────────────────────────────────
    # Philosophy: reward conversations and booked meetings heavily;
    # "Qualified" stage removed — meaningful conversation is the key gate.
    "weights": {
        "Call": {
            "Dial":                    1,
            "Connect":                 4,   # low — a connect alone means little
            "Meaningful Conversation": 18,  # real conversation required
            "Meeting Booked":          55,  # highest-value call outcome
        },
        "Email": {
            "Email Sent":     1,
            "Reply Received":  5,  # any reply
            "Positive Reply":  14, # genuine interest signal
            "Meeting Booked":  45, # confirmed meeting from email thread
        },
        "LinkedIn": {
            "Connection Request Sent": 1,
            "Connection Accepted":     3,   # passive acceptance
            "Reply to Message":        7,   # active engagement begins
            "Meeting Booked":          35,  # full conversion
        },
        "Meeting": {
            "Meeting Held": 30,  # completed, attended meeting
        },
    },
    "caps": {
        "Call":     {"Dial": 60},
        "Email":    {"Email Sent": 80},
        "LinkedIn": {"Connection Request Sent": 40},
    },
    "week_starts_monday": True,
}


# ── Connection ─────────────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


# ── Initialisation ────────────────────────────────────────────────────────────

def init_db() -> None:
    """Create all tables and seed default settings (idempotent)."""
    count_col_ddl = "\n".join(f"    {f}  INTEGER  DEFAULT 0," for f in COUNT_FIELDS)

    conn = _conn()
    conn.executescript(f"""
        CREATE TABLE IF NOT EXISTS daily_totals (
            id          INTEGER  PRIMARY KEY AUTOINCREMENT,
            date        TEXT     NOT NULL,
            rep_name    TEXT     NOT NULL,
            notes       TEXT     DEFAULT '',
            {count_col_ddl}
            created_at  TEXT     NOT NULL,
            updated_at  TEXT     NOT NULL,
            UNIQUE(date, rep_name)
        );
        CREATE INDEX IF NOT EXISTS idx_dt_date ON daily_totals (date);
        CREATE INDEX IF NOT EXISTS idx_dt_rep  ON daily_totals (rep_name);

        CREATE TABLE IF NOT EXISTS daily_proofs (
            id          INTEGER  PRIMARY KEY AUTOINCREMENT,
            daily_id    INTEGER  NOT NULL  REFERENCES daily_totals(id) ON DELETE CASCADE,
            step        TEXT     NOT NULL,
            file_path   TEXT     NOT NULL,
            created_at  TEXT     NOT NULL
        );

        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT  PRIMARY KEY,
            value TEXT  NOT NULL
        );
    """)
    conn.commit()
    conn.close()

    for k, v in DEFAULT_SETTINGS.items():
        if get_setting(k) is None:
            set_setting(k, v)

    # ── Weights migration ─────────────────────────────────────────────────────
    # Re-apply default weights when WEIGHTS_VERSION is bumped so existing
    # databases automatically adopt the new model on next startup.
    # Only weights are touched; all other settings (reps, caps, etc.) are left
    # exactly as-is.
    if get_setting("_weights_version") != WEIGHTS_VERSION:
        set_setting("weights", DEFAULT_SETTINGS["weights"])
        set_setting("_weights_version", WEIGHTS_VERSION)


# ── Settings ──────────────────────────────────────────────────────────────────

def get_setting(key: str, default=None):
    conn = _conn()
    row  = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return json.loads(row["value"]) if row else default


def set_setting(key: str, value) -> None:
    conn = _conn()
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)",
        (key, json.dumps(value)),
    )
    conn.commit()
    conn.close()


# ── Daily totals CRUD ─────────────────────────────────────────────────────────

def get_existing_row(date_val: str, rep_name: str) -> dict | None:
    """Return the existing daily_totals row for (date, rep), or None."""
    conn = _conn()
    row  = conn.execute(
        "SELECT * FROM daily_totals WHERE date=? AND rep_name=?",
        (date_val, rep_name),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def upsert_daily_total(
    date_val:        str,
    rep_name:        str,
    counts:          dict,
    notes:           str  = "",
    add_to_existing: bool = False,
) -> int:
    """
    Insert or update a daily_totals row.

    add_to_existing=True  → sums new counts onto the existing row.
    add_to_existing=False → overwrites existing counts (default).

    Returns the row id.
    """
    conn     = _conn()
    now      = datetime.now().isoformat()
    existing = conn.execute(
        "SELECT * FROM daily_totals WHERE date=? AND rep_name=?",
        (date_val, rep_name),
    ).fetchone()

    if existing:
        if add_to_existing:
            final = {f: (existing[f] or 0) + (counts.get(f, 0) or 0) for f in COUNT_FIELDS}
            final_notes = "\n".join(filter(None, [existing["notes"] or "", notes or ""]))
        else:
            final = {f: counts.get(f, 0) or 0 for f in COUNT_FIELDS}
            final_notes = notes if notes else (existing["notes"] or "")

        set_clause = ", ".join(f"{f}=?" for f in COUNT_FIELDS)
        vals = [final[f] for f in COUNT_FIELDS] + [final_notes, now, existing["id"]]
        conn.execute(
            f"UPDATE daily_totals SET {set_clause}, notes=?, updated_at=? WHERE id=?",
            vals,
        )
        row_id = existing["id"]
    else:
        cols  = ", ".join(COUNT_FIELDS)
        ph    = ", ".join("?" for _ in COUNT_FIELDS)
        vals  = [counts.get(f, 0) or 0 for f in COUNT_FIELDS]
        cur   = conn.execute(
            f"""INSERT INTO daily_totals
                    (date, rep_name, notes, {cols}, created_at, updated_at)
                VALUES (?,?,?,{ph},?,?)""",
            [date_val, rep_name, notes or ""] + vals + [now, now],
        )
        row_id = cur.lastrowid

    conn.commit()
    conn.close()
    return row_id


def get_daily_totals(
    start_date=None,
    end_date=None,
    rep_name: str = None,
    limit: int    = None,
) -> list:
    conn = _conn()
    q, p = "SELECT * FROM daily_totals WHERE 1=1", []
    if start_date:
        q += " AND date >= ?"; p.append(str(start_date))
    if end_date:
        q += " AND date <= ?"; p.append(str(end_date))
    if rep_name and rep_name != "All":
        q += " AND rep_name = ?"; p.append(rep_name)
    q += " ORDER BY date DESC, rep_name"
    if limit:
        q += f" LIMIT {limit}"
    rows = conn.execute(q, p).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_daily_total(row_id: int) -> None:
    conn = _conn()
    conn.execute("DELETE FROM daily_totals WHERE id=?", (row_id,))
    conn.commit()
    conn.close()


# ── Proofs ────────────────────────────────────────────────────────────────────

def add_proofs(daily_id: int, step: str, file_paths: list) -> None:
    """Associate proof file paths with a daily_totals row and step."""
    if not file_paths:
        return
    conn = _conn()
    now  = datetime.now().isoformat()
    conn.executemany(
        "INSERT INTO daily_proofs (daily_id, step, file_path, created_at) VALUES (?,?,?,?)",
        [(daily_id, step, p, now) for p in file_paths],
    )
    conn.commit()
    conn.close()


def get_proofs(daily_id: int) -> list:
    conn = _conn()
    rows = conn.execute(
        "SELECT * FROM daily_proofs WHERE daily_id=? ORDER BY step, created_at",
        (daily_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
