"""SQLite persistence for Panopti.

Everything the profile is built from lives in real tables, so the erasure
pipeline in this module deletes rows rather than hiding them. Run the app,
then open panopti.db with any SQLite browser and watch the rows appear and
disappear as you click around.
"""
import json
import sqlite3
import time
import hashlib
from contextlib import contextmanager

DB_PATH = "panopti.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
  sid TEXT PRIMARY KEY, created REAL, version INTEGER DEFAULT 1,
  consent TEXT DEFAULT '{}', restricted INTEGER DEFAULT 0,
  automated_stopped INTEGER DEFAULT 0, objected INTEGER DEFAULT 0,
  withdrawn INTEGER DEFAULT 0, erased INTEGER DEFAULT 0,
  erased_at REAL, wallet TEXT
);
CREATE TABLE IF NOT EXISTS identity (
  id INTEGER PRIMARY KEY AUTOINCREMENT, sid TEXT, field TEXT, value TEXT,
  captured_by TEXT, first_seen REAL, updated REAL,
  UNIQUE (sid, field, value)
);
CREATE TABLE IF NOT EXISTS device (
  sid TEXT PRIMARY KEY, payload TEXT, ip TEXT, updated REAL
);
CREATE TABLE IF NOT EXISTS telemetry (
  sid TEXT PRIMARY KEY, travel_px REAL DEFAULT 0, samples INTEGER DEFAULT 0,
  speed REAL DEFAULT 0, x INTEGER DEFAULT 0, y INTEGER DEFAULT 0,
  clicks INTEGER DEFAULT 0, rage INTEGER DEFAULT 0, scroll_max REAL DEFAULT 0,
  keystrokes INTEGER DEFAULT 0, backspaces INTEGER DEFAULT 0, copies INTEGER DEFAULT 0,
  blurs INTEGER DEFAULT 0, blur_ms REAL DEFAULT 0, last_seen REAL
);
CREATE TABLE IF NOT EXISTS views (
  sid TEXT, token_id TEXT, views INTEGER DEFAULT 0, dwell_ms REAL DEFAULT 0,
  PRIMARY KEY (sid, token_id)
);
CREATE TABLE IF NOT EXISTS searches (
  id INTEGER PRIMARY KEY AUTOINCREMENT, sid TEXT, ts REAL, q TEXT
);
CREATE TABLE IF NOT EXISTS cart (
  sid TEXT, token_id TEXT, qty INTEGER, PRIMARY KEY (sid, token_id)
);
CREATE TABLE IF NOT EXISTS orders (
  id INTEGER PRIMARY KEY AUTOINCREMENT, sid TEXT, ts REAL, total REAL,
  items TEXT, name TEXT, addr TEXT
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, sid TEXT, ts REAL, type TEXT, detail TEXT
);
CREATE TABLE IF NOT EXISTS inferences (
  sid TEXT, key TEXT, value TEXT, confidence REAL, note TEXT, computed REAL,
  PRIMARY KEY (sid, key)
);
CREATE TABLE IF NOT EXISTS wallet_links (
  sid TEXT, address TEXT, linked_name TEXT, ts REAL, PRIMARY KEY (sid, address)
);
CREATE TABLE IF NOT EXISTS exports (
  id INTEGER PRIMARY KEY AUTOINCREMENT, sid TEXT, ts REAL, recipient TEXT, summary TEXT
);
CREATE TABLE IF NOT EXISTS suppression (
  hash TEXT PRIMARY KEY, created REAL
);
CREATE TABLE IF NOT EXISTS signals (
  sid TEXT, key TEXT, value TEXT, hits INTEGER DEFAULT 1,
  first_seen REAL, updated REAL, PRIMARY KEY (sid, key)
);
CREATE TABLE IF NOT EXISTS points (
  id INTEGER PRIMARY KEY AUTOINCREMENT, sid TEXT, ts REAL, reason TEXT, amount INTEGER
);
CREATE TABLE IF NOT EXISTS rewards (
  sid TEXT, tier TEXT, redeemed_at REAL, PRIMARY KEY (sid, tier)
);
CREATE TABLE IF NOT EXISTS ad_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, sid TEXT, ts REAL, ad_id TEXT,
  kind TEXT, advertiser TEXT, segment TEXT, revenue REAL DEFAULT 0, targeted INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS observations (
  id INTEGER PRIMARY KEY AUTOINCREMENT, sid TEXT, ts REAL,
  key TEXT, text TEXT, tier INTEGER DEFAULT 0
);
"""


@contextmanager
def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


IDENTITY_DDL = """
CREATE TABLE IF NOT EXISTS identity (
  id INTEGER PRIMARY KEY AUTOINCREMENT, sid TEXT, field TEXT, value TEXT,
  captured_by TEXT, first_seen REAL, updated REAL,
  UNIQUE (sid, field, value)
);
"""


def _migrate_identity(con):
    """Upgrade a pre-existing database from the old one-row-per-session identity
    table to the append-only one.

    Earlier versions stored a single row per session with a column per field, so
    a correction overwrote the previous value. The current version keeps every
    value as its own row. Without this, an old panopti.db fails at startup on
    `no such column: field`, which is a miserable first impression.
    """
    row = con.execute("SELECT name FROM sqlite_master WHERE type='table' "
                      "AND name='identity'").fetchone()
    if not row:
        return
    cols = [r[1] for r in con.execute("PRAGMA table_info(identity)")]
    if "field" in cols:
        return                              # already the new shape

    con.execute("ALTER TABLE identity RENAME TO identity_legacy")
    con.executescript(IDENTITY_DDL)
    carry = [c for c in ("name", "email", "phone", "addr1", "city", "zip") if c in cols]
    now = time.time()
    moved = 0
    for r in con.execute("SELECT * FROM identity_legacy"):
        for c in carry:
            v = r[c]
            if v is None or not str(v).strip():
                continue
            con.execute(
                "INSERT OR IGNORE INTO identity "
                "(sid,field,value,captured_by,first_seen,updated) VALUES (?,?,?,?,?,?)",
                (r["sid"], c, str(v).strip()[:160],
                 (r["captured_by"] if "captured_by" in cols else None) or "migrated",
                 (r["updated"] if "updated" in cols else now) or now, now))
            moved += 1
    con.execute("DROP TABLE identity_legacy")
    print("  migrated %d identity value%s to the append-only table"
          % (moved, "" if moved == 1 else "s"))


def init():
    with db() as con:
        _migrate_identity(con)
        con.executescript(SCHEMA)
        con.execute("CREATE INDEX IF NOT EXISTS identity_sid ON identity (sid, field)")


# --------------------------------------------------------------------------
# session
# --------------------------------------------------------------------------
DEFAULT_CONSENT = {"decided": False, "analytics": False, "ads": False,
                   "profiling": False, "share": False, "essential": True}


def ensure_session(sid, version=1):
    with db() as con:
        row = con.execute("SELECT sid FROM sessions WHERE sid=?", (sid,)).fetchone()
        if not row:
            con.execute(
                "INSERT INTO sessions (sid, created, version, consent) VALUES (?,?,?,?)",
                (sid, time.time(), version, json.dumps(DEFAULT_CONSENT)))
            con.execute("INSERT OR IGNORE INTO telemetry (sid, last_seen) VALUES (?,?)",
                        (sid, time.time()))


def get_session(sid):
    with db() as con:
        r = con.execute("SELECT * FROM sessions WHERE sid=?", (sid,)).fetchone()
        return dict(r) if r else None


def set_session(sid, **fields):
    if not fields:
        return
    cols = ", ".join("%s=?" % k for k in fields)
    with db() as con:
        con.execute("UPDATE sessions SET %s WHERE sid=?" % cols,
                    tuple(fields.values()) + (sid,))


def set_consent(sid, consent):
    set_session(sid, consent=json.dumps(consent))


def get_consent(sid):
    s = get_session(sid) or {}
    try:
        return json.loads(s.get("consent") or "{}") or dict(DEFAULT_CONSENT)
    except ValueError:
        return dict(DEFAULT_CONSENT)


def reset_session(sid, version):
    """Start a clean session, keeping the same sid. Used by the version switch."""
    wipe(sid, keep_orders=False)
    with db() as con:
        con.execute("DELETE FROM sessions WHERE sid=?", (sid,))
        con.execute("DELETE FROM orders WHERE sid=?", (sid,))
    ensure_session(sid, version)
    set_session(sid, version=version)


# --------------------------------------------------------------------------
# ingest
# --------------------------------------------------------------------------
def save_device(sid, payload, ip):
    with db() as con:
        con.execute("INSERT INTO device (sid, payload, ip, updated) VALUES (?,?,?,?) "
                    "ON CONFLICT(sid) DO UPDATE SET payload=excluded.payload, "
                    "ip=excluded.ip, updated=excluded.updated",
                    (sid, json.dumps(payload), ip, time.time()))


def get_device(sid):
    with db() as con:
        r = con.execute("SELECT payload, ip FROM device WHERE sid=?", (sid,)).fetchone()
        if not r:
            return {}, None
        return json.loads(r["payload"]), r["ip"]


def bump_telemetry(sid, t):
    with db() as con:
        con.execute("""
          INSERT INTO telemetry (sid,travel_px,samples,speed,x,y,clicks,rage,scroll_max,
                                 keystrokes,backspaces,copies,blurs,blur_ms,last_seen)
          VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
          ON CONFLICT(sid) DO UPDATE SET
            travel_px = travel_px + excluded.travel_px,
            samples   = samples   + excluded.samples,
            speed     = excluded.speed,
            x = excluded.x, y = excluded.y,
            clicks     = clicks     + excluded.clicks,
            rage       = rage       + excluded.rage,
            scroll_max = MAX(scroll_max, excluded.scroll_max),
            keystrokes = keystrokes + excluded.keystrokes,
            backspaces = backspaces + excluded.backspaces,
            copies     = copies     + excluded.copies,
            blurs      = blurs      + excluded.blurs,
            blur_ms    = blur_ms    + excluded.blur_ms,
            last_seen  = excluded.last_seen
        """, (sid, t.get("travel", 0), t.get("samples", 0), t.get("speed", 0),
              t.get("x", 0), t.get("y", 0), t.get("clicks", 0), t.get("rage", 0),
              t.get("scroll", 0), t.get("keys", 0), t.get("backspaces", 0),
              t.get("copies", 0), t.get("blurs", 0), t.get("blurMs", 0), time.time()))


def get_telemetry(sid):
    with db() as con:
        r = con.execute("SELECT * FROM telemetry WHERE sid=?", (sid,)).fetchone()
        return dict(r) if r else {}


def bump_views(sid, views):
    """views: {token_id: {"v": n, "d": ms}}"""
    with db() as con:
        for tid, d in views.items():
            con.execute("""
              INSERT INTO views (sid, token_id, views, dwell_ms) VALUES (?,?,?,?)
              ON CONFLICT(sid, token_id) DO UPDATE SET
                views = views + excluded.views, dwell_ms = dwell_ms + excluded.dwell_ms
            """, (sid, tid, int(d.get("v", 0)), float(d.get("d", 0))))


def get_views(sid):
    with db() as con:
        return [dict(r) for r in con.execute(
            "SELECT token_id, views, dwell_ms FROM views WHERE sid=? ORDER BY dwell_ms DESC",
            (sid,))]


def add_search(sid, q):
    with db() as con:
        con.execute("INSERT INTO searches (sid, ts, q) VALUES (?,?,?)", (sid, time.time(), q))


def get_searches(sid):
    with db() as con:
        return [r["q"] for r in con.execute(
            "SELECT q FROM searches WHERE sid=? ORDER BY id", (sid,))]


def set_cart(sid, token_id, qty):
    with db() as con:
        if qty <= 0:
            con.execute("DELETE FROM cart WHERE sid=? AND token_id=?", (sid, token_id))
        else:
            con.execute("INSERT INTO cart (sid, token_id, qty) VALUES (?,?,?) "
                        "ON CONFLICT(sid, token_id) DO UPDATE SET qty=excluded.qty",
                        (sid, token_id, qty))


def get_cart(sid):
    with db() as con:
        return [dict(r) for r in con.execute(
            "SELECT token_id, qty FROM cart WHERE sid=?", (sid,))]


def clear_cart(sid):
    with db() as con:
        con.execute("DELETE FROM cart WHERE sid=?", (sid,))


IDENTITY_FIELDS = ("name", "email", "phone", "addr1", "city", "zip")


def save_identity(sid, fields, captured_by):
    """Append values rather than overwrite them.

    People have more than one email address, change their name, move house, and
    mistype things before they get them right. A surveillance database keeps all
    of it, so this one does too: every distinct value a field has ever held stays
    as its own row, with how we got it and when we first saw it.
    """
    now = time.time()
    with db() as con:
        for field, value in fields.items():
            if field not in IDENTITY_FIELDS:
                continue
            value = (value or "").strip()
            if not value:
                continue
            con.execute(
                "INSERT INTO identity (sid,field,value,captured_by,first_seen,updated) "
                "VALUES (?,?,?,?,?,?) "
                "ON CONFLICT(sid,field,value) DO UPDATE SET updated=excluded.updated",
                (sid, field, value[:160], captured_by, now, now))


def save_identity_partial(sid, field, value, captured_by):
    """Keystroke capture: replace the growing prefix instead of keeping every
    half-typed fragment, but still keep earlier *completed* values."""
    value = (value or "").strip()[:160]
    if field not in IDENTITY_FIELDS:
        return
    now = time.time()
    with db() as con:
        rows = con.execute("SELECT id, value FROM identity WHERE sid=? AND field=? "
                           "AND captured_by LIKE 'keystroke%' ORDER BY id DESC",
                           (sid, field)).fetchall()
        # collapse a row that is a prefix of what is now being typed
        for r in rows:
            if value.startswith(r["value"]) or r["value"].startswith(value):
                con.execute("DELETE FROM identity WHERE id=?", (r["id"],))
        if value:
            con.execute(
                "INSERT INTO identity (sid,field,value,captured_by,first_seen,updated) "
                "VALUES (?,?,?,?,?,?) "
                "ON CONFLICT(sid,field,value) DO UPDATE SET updated=excluded.updated",
                (sid, field, value, captured_by, now, now))


def get_identity_multi(sid):
    """{field: [{value, captured_by, first_seen}, ...]} — every value ever held."""
    out = {}
    with db() as con:
        for r in con.execute("SELECT field, value, captured_by, first_seen FROM identity "
                             "WHERE sid=? ORDER BY field, id", (sid,)):
            out.setdefault(r["field"], []).append(
                {"value": r["value"], "captured_by": r["captured_by"],
                 "first_seen": r["first_seen"]})
    return out


def get_identity(sid):
    """The single most recent value per field, for code that wants one string."""
    out = {}
    with db() as con:
        for r in con.execute("SELECT field, value FROM identity WHERE sid=? ORDER BY id",
                             (sid,)):
            out[r["field"]] = r["value"]
    return out


# --------------------------------------------------------------------------
# signals and the observation log
# --------------------------------------------------------------------------
def record_signals(sid, pairs):
    """Upsert raw signals. `pairs` is [(key, value), ...]. Returns new keys."""
    now = time.time()
    fresh = []
    with db() as con:
        for key, value in pairs:
            key = str(key)[:60]
            value = "" if value is None else str(value)[:200]
            row = con.execute("SELECT hits, value FROM signals WHERE sid=? AND key=?",
                              (sid, key)).fetchone()
            if row is None:
                con.execute("INSERT INTO signals (sid,key,value,hits,first_seen,updated) "
                            "VALUES (?,?,?,1,?,?)", (sid, key, value, now, now))
                fresh.append(key)
            else:
                con.execute("UPDATE signals SET value=?, hits=hits+1, updated=? "
                            "WHERE sid=? AND key=?", (value, now, sid, key))
    return fresh


def get_signals(sid):
    with db() as con:
        return {r["key"]: {"value": r["value"], "hits": r["hits"],
                           "first_seen": r["first_seen"]}
                for r in con.execute("SELECT * FROM signals WHERE sid=? ORDER BY key", (sid,))}


def add_observation(sid, key, text, tier=0):
    with db() as con:
        con.execute("INSERT INTO observations (sid,ts,key,text,tier) VALUES (?,?,?,?,?)",
                    (sid, time.time(), key[:60], text[:400], int(tier)))


def get_observations(sid, limit=400, since_id=0):
    with db() as con:
        return [dict(r) for r in con.execute(
            "SELECT id, ts, key, text, tier FROM observations WHERE sid=? AND id>? "
            "ORDER BY id DESC LIMIT ?", (sid, since_id, limit))]


def count_observations(sid):
    with db() as con:
        return con.execute("SELECT COUNT(*) c FROM observations WHERE sid=?",
                           (sid,)).fetchone()["c"]


def award_points(sid, reason, amount):
    """Engagement pays, in a currency we mint ourselves and value at nothing."""
    if not amount:
        return
    with db() as con:
        con.execute("INSERT INTO points (sid,ts,reason,amount) VALUES (?,?,?,?)",
                    (sid, time.time(), reason[:60], int(amount)))


def points_total(sid):
    with db() as con:
        r = con.execute("SELECT COALESCE(SUM(amount),0) t FROM points WHERE sid=?",
                        (sid,)).fetchone()
        return r["t"] or 0


def points_breakdown(sid):
    with db() as con:
        return [{"reason": r["reason"], "points": r["p"], "times": r["n"]}
                for r in con.execute(
                    "SELECT reason, SUM(amount) p, COUNT(*) n FROM points WHERE sid=? "
                    "GROUP BY reason ORDER BY p DESC", (sid,))]


def redeem(sid, tier):
    with db() as con:
        con.execute("INSERT OR IGNORE INTO rewards (sid,tier,redeemed_at) VALUES (?,?,?)",
                    (sid, tier, time.time()))


def get_rewards(sid):
    with db() as con:
        return [r["tier"] for r in con.execute(
            "SELECT tier FROM rewards WHERE sid=? ORDER BY redeemed_at", (sid,))]


def add_ad_event(sid, ad, kind, revenue, targeted=True):
    with db() as con:
        con.execute("INSERT INTO ad_events (sid,ts,ad_id,kind,advertiser,segment,revenue,targeted) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (sid, time.time(), ad.get("id"), kind, ad.get("advertiser"),
                     ad.get("segment"), float(revenue or 0), 1 if targeted else 0))


def get_ad_events(sid):
    with db() as con:
        return [dict(r) for r in con.execute(
            "SELECT * FROM ad_events WHERE sid=? ORDER BY id", (sid,))]


def ad_summary(sid):
    with db() as con:
        r = con.execute(
            "SELECT COUNT(*) n, "
            "SUM(CASE WHEN kind='impression' THEN 1 ELSE 0 END) imps, "
            "SUM(CASE WHEN kind='click' THEN 1 ELSE 0 END) clicks, "
            "SUM(revenue) rev, "
            "SUM(CASE WHEN kind='impression' AND targeted=1 THEN 1 ELSE 0 END) targeted "
            "FROM ad_events WHERE sid=?", (sid,)).fetchone()
        return {"events": r["n"] or 0, "impressions": r["imps"] or 0,
                "clicks": r["clicks"] or 0, "revenue": round(r["rev"] or 0, 4),
                "targeted": r["targeted"] or 0}


def link_wallet(sid, address, name=None):
    with db() as con:
        con.execute("INSERT INTO wallet_links (sid,address,linked_name,ts) VALUES (?,?,?,?) "
                    "ON CONFLICT(sid,address) DO UPDATE SET linked_name=excluded.linked_name",
                    (sid, address, name, time.time()))


def get_wallet_links(sid):
    with db() as con:
        return [dict(r) for r in con.execute(
            "SELECT address, linked_name, ts FROM wallet_links WHERE sid=?", (sid,))]


def add_order(sid, total, items, name, addr):
    with db() as con:
        cur = con.execute("INSERT INTO orders (sid,ts,total,items,name,addr) VALUES (?,?,?,?,?,?)",
                          (sid, time.time(), total, json.dumps(items), name, addr))
        return cur.lastrowid


def get_orders(sid):
    with db() as con:
        return [dict(r) for r in con.execute(
            "SELECT id, ts, total, items, name, addr FROM orders WHERE sid=? ORDER BY id", (sid,))]


def add_event(sid, type_, detail=""):
    with db() as con:
        con.execute("INSERT INTO events (sid,ts,type,detail) VALUES (?,?,?,?)",
                    (sid, time.time(), type_, detail))


def get_events(sid, limit=500):
    with db() as con:
        return [dict(r) for r in con.execute(
            "SELECT ts, type, detail FROM events WHERE sid=? ORDER BY id DESC LIMIT ?",
            (sid, limit))]


def count_events(sid):
    with db() as con:
        return con.execute("SELECT COUNT(*) c FROM events WHERE sid=?", (sid,)).fetchone()["c"]


def save_inferences(sid, inf):
    """Persist derived data, so that erasing it later means deleting real rows."""
    with db() as con:
        for k, v in inf.items():
            if not isinstance(v, dict):
                continue
            con.execute("""
              INSERT INTO inferences (sid,key,value,confidence,note,computed)
              VALUES (?,?,?,?,?,?)
              ON CONFLICT(sid,key) DO UPDATE SET value=excluded.value,
                confidence=excluded.confidence, note=excluded.note, computed=excluded.computed
            """, (sid, k, str(v.get("value")), float(v.get("confidence") or 0),
                  json.dumps({x: y for x, y in v.items() if x not in ("value", "confidence")}),
                  time.time()))


def get_inferences(sid):
    with db() as con:
        return [dict(r) for r in con.execute(
            "SELECT key, value, confidence, note FROM inferences WHERE sid=?", (sid,))]


def drop_inferences(sid):
    with db() as con:
        return con.execute("DELETE FROM inferences WHERE sid=?", (sid,)).rowcount


def record_export(sid, recipient, summary):
    with db() as con:
        con.execute("INSERT INTO exports (sid,ts,recipient,summary) VALUES (?,?,?,?)",
                    (sid, time.time(), recipient, summary))


def get_exports(sid):
    with db() as con:
        return [dict(r) for r in con.execute(
            "SELECT recipient, ts, summary FROM exports WHERE sid=?", (sid,))]


# --------------------------------------------------------------------------
# erasure — every step below runs real SQL and reports real row counts
# --------------------------------------------------------------------------
def _del(con, table, sid):
    return con.execute("DELETE FROM %s WHERE sid=?" % table, (sid,)).rowcount


ERASURE_STEPS = [
    ("ad_events",     "advertising impressions, clicks and revenue", "ad_events"),
    ("points",        "your loyalty points ledger",              "points"),
    ("rewards",       "rewards you redeemed",                    "rewards"),
    ("signals",       "every signal your browser emitted",       "signals"),
    ("observations",  "the narrated observation log",            "observations"),
    ("telemetry",     "cursor and interaction telemetry",        "telemetry"),
    ("events",        "event stream",                            "events"),
    ("views",         "token view and dwell history",            "views"),
    ("searches",      "search history",                          "searches"),
    ("inferences",    "derived segments and inferences",         "inferences"),
    ("wallet_links",  "wallet address cluster",                  "wallet_links"),
    ("exports",       "partner transfer log (recipients notified)", "exports"),
    ("cart",          "abandoned cart",                          "cart"),
    ("device",        "device fingerprint and network record",   "device"),
    ("identity",      "every name, email, address and phone ever typed", "identity"),
]
RETAINED_STEPS = [
    ("orders",      "mint invoices and tax records", "RETAINED — legal obligation, 6 years"),
    ("suppression", "suppression hash (so you are never re-profiled)",
                    "RETAINED — to give effect to this erasure"),
]


def erasure_plan():
    steps = [{"key": k, "label": lab, "kind": "delete"} for k, lab, _ in ERASURE_STEPS]
    steps += [{"key": k, "label": lab, "kind": "retain", "why": why}
              for k, lab, why in RETAINED_STEPS]
    steps.append({"key": "__finalise", "label": "session record", "kind": "delete"})
    return steps


def erase_step(sid, index):
    """Run exactly one step of the pipeline. Returns what actually happened."""
    plan = erasure_plan()
    if index < 0 or index >= len(plan):
        return {"done": True}
    step = plan[index]

    if step["kind"] == "retain":
        if step["key"] == "suppression":
            h = hashlib.sha256(("suppress:" + sid).encode()).hexdigest()
            with db() as con:
                con.execute("INSERT OR IGNORE INTO suppression (hash, created) VALUES (?,?)",
                            (h, time.time()))
            return dict(step, rows=1, detail="hash %s… written" % h[:12])
        with db() as con:
            n = con.execute("SELECT COUNT(*) c FROM orders WHERE sid=?", (sid,)).fetchone()["c"]
        return dict(step, rows=n, detail="%d row%s kept" % (n, "" if n == 1 else "s"))

    if step["key"] == "__finalise":
        with db() as con:
            con.execute("UPDATE sessions SET erased=1, erased_at=?, wallet=NULL, "
                        "consent=?, restricted=0, automated_stopped=0 WHERE sid=?",
                        (time.time(), json.dumps(DEFAULT_CONSENT), sid))
        return dict(step, rows=1, detail="marked erased, profile cleared")

    table = dict((k, t) for k, _, t in ERASURE_STEPS)[step["key"]]
    with db() as con:
        n = _del(con, table, sid)
    return dict(step, rows=n, detail="%d row%s dropped" % (n, "" if n == 1 else "s"))


def wipe(sid, keep_orders=True):
    """Drop everything for a session. Used by erasure and by the version switch."""
    tables = ["telemetry", "events", "views", "searches", "inferences",
              "wallet_links", "exports", "cart", "device", "identity",
              "signals", "observations", "ad_events", "points", "rewards"]
    if not keep_orders:
        tables.append("orders")
    with db() as con:
        for t in tables:
            _del(con, t, sid)


def table_counts(sid):
    """Live row counts, so the interface can show the database emptying."""
    out = {}
    with db() as con:
        for t in ("identity", "device", "telemetry", "views", "searches", "cart",
                  "orders", "events", "inferences", "wallet_links", "exports",
                  "signals", "observations", "ad_events", "points", "rewards"):
            out[t] = con.execute("SELECT COUNT(*) c FROM %s WHERE sid=?" % t,
                                 (sid,)).fetchone()["c"]
        out["suppression"] = con.execute("SELECT COUNT(*) c FROM suppression").fetchone()["c"]
    return out
