"""Panopti — a marketplace that watches you, and a version of it that does not.

    pip install -r requirements.txt
    python app.py
    open http://127.0.0.1:5000

Everything the right-hand panel shows is read back out of panopti.db. Delete
the file to start completely fresh.
"""
import hashlib
import json
import os
import time
import uuid

from flask import (Flask, jsonify, make_response, render_template, request,
                   send_file, session)

import ads
import config
import narrate
import partners
import policy_text
import store
import tunnel
from catalog import (PRODUCTS, art_svg, catalog_payload, token_detail,
                     token_hash, token_hash_short)
from profiler import build_dossier, compute_inferences, signal_counts, BUYERS

app = Flask(__name__)
app.secret_key = config.secret_key()

PAUSE_SIGNAL = "USER SELECTED PAUSE."
STOP_SIGNAL = "USER SELECTED STOP."

store.init()


def sid():
    if "sid" not in session:
        session["sid"] = uuid.uuid4().hex
        session.permanent = False
    store.ensure_session(session["sid"])
    return session["sid"]


def state(s):
    row = store.get_session(s) or {}
    return {
        "version": row.get("version", 1),
        "restricted": bool(row.get("restricted")),
        "automated_stopped": bool(row.get("automated_stopped")),
        "objected": bool(row.get("objected")),
        "withdrawn": bool(row.get("withdrawn")),
        "erased": bool(row.get("erased")),
        "wallet": row.get("wallet"),
        "consent": store.get_consent(s),
    }


def envelope(s, since=0):
    return {"dossier": build_dossier(s), "state": state(s),
            "cart": store.get_cart(s), "events": store.count_events(s),
            "feed": store.get_observations(s, 60, since),
            "feed_total": store.count_observations(s)}


# --------------------------------------------------------------------------
@app.route("/")
def index():
    s = sid()
    return render_template("index.html",
                           catalog=catalog_payload(),
                           state=state(s),
                           token_count=len(PRODUCTS))


@app.get("/api/token/<tid>")
def api_token(tid):
    """The large view. Looking closely is itself a signal, so it is logged."""
    d = token_detail(tid)
    if not d:
        return jsonify({"error": "unknown token"}), 404
    s = sid()
    row = store.get_session(s) or {}
    if not row.get("erased") and not row.get("restricted"):
        store.bump_views(s, {tid: {"v": 1, "d": 1500}})
        _award(s, "opened a token full size")
        store.add_event(s, "token_opened", tid)
        store.record_signals(s, [("token.opened", d["name"])])
    return jsonify(dict(d, envelope=envelope(s)))


@app.route("/art/<tid>.svg")
def art(tid):
    if tid not in PRODUCTS:
        return "not found", 404
    r = make_response(art_svg(tid))
    r.headers["Content-Type"] = "image/svg+xml"
    r.headers["Cache-Control"] = "public, max-age=86400"
    return r


@app.route("/api/state")
def api_state():
    return jsonify(envelope(sid()))


@app.post("/api/device")
def api_device():
    s = sid()
    store.save_device(s, request.json or {}, request.remote_addr)
    store.add_event(s, "device_fingerprinted", (request.json or {}).get("fingerprintId", ""))
    return jsonify(envelope(s))


@app.post("/api/observe")
def api_observe():
    """The firehose.

    The browser reports signals as bare keys and values; the sentences are
    written on the server by narrate.py. A signal is narrated the first time it
    is seen, and afterwards only when it is marked `always` or its value moved.
    Article 18 refuses everything that is not strictly necessary; Article 22
    refuses anything that draws a conclusion.
    """
    s = sid()
    row = store.get_session(s) or {}
    if row.get("erased"):
        return jsonify(envelope(s))

    restricted = bool(row.get("restricted"))
    stopped = bool(row.get("automated_stopped"))
    body = request.json or {}
    incoming = body.get("signals") or []
    since = int(body.get("since") or 0)

    accepted, refused = [], 0
    for item in incoming:
        key = str(item.get("k", ""))[:60]
        if not key:
            continue
        essential = key.startswith(("visit.", "win.size", "dev.browser", "dev.screen"))
        if restricted and not essential:
            refused += 1
            continue
        # Art. 22 stops the part that reaches a conclusion, not the part that counts clicks
        _tpl, tier = narrate.TEMPLATES.get(key, (None, 0))
        if stopped and tier >= 3:
            refused += 1
            continue
        accepted.append(item)

    if refused and restricted:
        store.record_signals(s, [("art18.refused", PAUSE_SIGNAL)])
    if refused and stopped and not restricted:
        store.record_signals(s, [("art22.refused", STOP_SIGNAL)])

    fresh = store.record_signals(s, [(i["k"], i.get("v")) for i in accepted])
    freshset = set(fresh)
    for item in accepted:
        key = item["k"]
        if (key in freshset or item.get("always")) and narrate.is_milestone(key):
            text, tier = narrate.render(key, item.get("v"), item.get("v2"))
            store.add_observation(s, key, text, tier)

    return jsonify(dict(envelope(s, since), refused=refused,
                        reason=(PAUSE_SIGNAL if restricted else
                                (STOP_SIGNAL if stopped and refused else None))))


@app.get("/api/feed")
def api_feed():
    s = sid()
    since = int(request.args.get("since") or 0)
    return jsonify({"feed": store.get_observations(s, 120, since),
                    "total": store.count_observations(s)})


@app.post("/api/track")
def api_track():
    """The beacon. Honours Art. 18 by refusing the data, not by hiding it."""
    s = sid()
    row = store.get_session(s) or {}
    if row.get("erased"):
        return jsonify(envelope(s))
    body = request.json or {}

    if row.get("restricted"):
        # strictly necessary only: we accept nothing optional while restricted
        return jsonify(dict(envelope(s), ingested=False, reason="USER SELECTED PAUSE."))

    t = body.get("t") or {}
    if any(t.values()):
        store.bump_telemetry(s, t)
    if body.get("views"):
        store.bump_views(s, body["views"])
        _award(s, "looked at a token", len(body["views"]))
    if (t.get("scroll_max") or 0) > 40:
        _award(s, "scrolled the catalogue")
    for q in body.get("searches") or []:
        _award(s, "searched")
        store.add_search(s, q[:120])
        store.add_event(s, "search", q[:120])
    for e in body.get("events") or []:
        store.add_event(s, str(e.get("type"))[:40], str(e.get("detail"))[:120])

    # v1 logs an onward transfer every few interactions, so the export table fills up
    if row.get("version", 1) == 1 and (t.get("clicks") or body.get("views")):
        n = len(store.get_exports(s))
        if n < len(BUYERS):
            store.record_export(s, BUYERS[n], "identifiers, behaviour and derived segments")
    return jsonify(envelope(s))


@app.post("/api/version")
def api_version():
    s = sid()
    v = 2 if int((request.json or {}).get("version", 1)) == 2 else 1
    store.reset_session(s, v)
    return jsonify(envelope(s))


@app.post("/api/reset")
def api_reset():
    s = sid()
    v = (store.get_session(s) or {}).get("version", 1)
    store.reset_session(s, v)
    return jsonify(envelope(s))


@app.post("/api/consent")
def api_consent():
    s = sid()
    body = request.json or {}
    c = store.get_consent(s)
    for k in ("analytics", "ads", "profiling", "share"):
        if k in body:
            c[k] = bool(body[k])
    c["decided"] = True
    store.set_consent(s, c)
    store.add_event(s, "consent", json.dumps({k: c[k] for k in
                                              ("analytics", "ads", "profiling", "share")}))
    return jsonify(envelope(s))


@app.post("/api/cart")
def api_cart():
    s = sid()
    body = request.json or {}
    tid = body.get("token_id")
    if tid not in PRODUCTS:
        return jsonify({"error": "unknown token"}), 400
    cur = {c["token_id"]: c["qty"] for c in store.get_cart(s)}
    qty = cur.get(tid, 0) + 1 if body.get("op") == "add" else 0
    store.set_cart(s, tid, qty)
    store.add_event(s, "cart_" + (body.get("op") or "set"), tid)
    if body.get("op") == "add":
        _award(s, "added to cart")
    if body.get("op") == "add" and not (store.get_session(s) or {}).get("restricted"):
        store.bump_views(s, {tid: {"v": 1, "d": 0}})
    return jsonify(envelope(s))


@app.post("/api/checkout/field")
def api_field():
    """v1 writes every keystroke straight to the database. v2 waits for submit."""
    s = sid()
    row = store.get_session(s) or {}
    if row.get("version", 1) != 1 or row.get("erased"):
        return jsonify({"ignored": True})
    body = request.json or {}
    store.save_identity_partial(s, body.get("field"), body.get("value", ""),
                                "keystroke capture, before submit")
    return jsonify(envelope(s))


@app.post("/api/wallet")
def api_wallet():
    s = sid()
    addr = (request.json or {}).get("address", "")[:44]
    store.set_session(s, wallet=addr)
    store.link_wallet(s, addr, (store.get_identity(s) or {}).get("name"))
    store.add_event(s, "wallet_connected", addr[:12])
    return jsonify(envelope(s))


@app.post("/api/order")
def api_order():
    """A real checkout against a fake shop: nothing is charged, everything is logged.

    Each field arrives as a list, because people genuinely do have several email
    addresses and more than one name. Every value is kept as its own row.
    """
    s = sid()
    body = request.json or {}
    fields = {}
    for k in ("name", "email", "phone", "addr1", "city", "zip"):
        raw = body.get(k)
        vals = raw if isinstance(raw, list) else [raw]
        fields[k] = [str(v).strip()[:160] for v in vals if v and str(v).strip()]
    for k, vals in fields.items():
        for v in vals:
            store.save_identity(s, {k: v}, "submitted at checkout")
    primary = {k: (v[0] if v else "") for k, v in fields.items()}
    cart = store.get_cart(s)
    if not cart:
        return jsonify({"error": "empty cart"}), 400
    items = [{"token": PRODUCTS[c["token_id"]]["n"], "qty": c["qty"],
              "usd": PRODUCTS[c["token_id"]]["p"],
              "hash": token_hash_short(c["token_id"])}
             for c in cart if c["token_id"] in PRODUCTS]
    total = sum(i["usd"] * i["qty"] for i in items)
    oid = store.add_order(s, total, items, primary["name"],
                          ", ".join(x for x in (primary["addr1"], primary["city"]) if x))

    # No wallet to connect: we issue a custodial one and link it to every name given.
    w = (store.get_session(s) or {}).get("wallet")
    if not w:
        w = "0x" + hashlib.sha256(("custodial:" + s).encode()).hexdigest()[:40]
        store.set_session(s, wallet=w)
        store.add_event(s, "custodial_wallet_issued", w[:12])
    for n in (fields["name"] or [None]):
        store.link_wallet(s, w, n)

    store.clear_cart(s)
    _award(s, "completed a purchase")
    store.add_event(s, "purchase", "order %d, $%s, %d value(s) stored"
                    % (oid, format(total, ","), sum(len(v) for v in fields.values())))
    return jsonify(dict(envelope(s), order_id=oid, total=total, items=items, wallet=w))


# --------------------------------------------------------------------------
# rights
# --------------------------------------------------------------------------
@app.post("/api/rights/restrict")
def r_restrict():
    """Art. 18 — stop optional processing, keep strictly necessary processing."""
    s = sid()
    row = store.get_session(s) or {}
    on = 0 if row.get("restricted") else 1
    store.set_session(s, restricted=on)
    store.add_event(s, "art18_restriction", "USER SELECTED PAUSE." if on else "lifted")
    return jsonify(dict(envelope(s), restricted=bool(on),
                        signal="USER SELECTED PAUSE." if on else "restriction lifted"))


@app.post("/api/rights/automated")
def r_automated():
    """Art. 22 — stop the guessing, and empty the table it was written to."""
    s = sid()
    row = store.get_session(s) or {}
    on = 0 if row.get("automated_stopped") else 1
    store.set_session(s, automated_stopped=on)
    dropped = store.drop_inferences(s) if on else 0
    store.add_event(s, "art22_automated", "USER SELECTED STOP." if on else "resumed")
    return jsonify(dict(envelope(s), automated_stopped=bool(on), rows_dropped=dropped,
                        signal="USER SELECTED STOP." if on else "automated decisions resumed"))


@app.post("/api/rights/object")
def r_object():
    s = sid()
    c = store.get_consent(s)
    c["profiling"] = False
    c["ads"] = False
    store.set_consent(s, c)
    store.set_session(s, objected=1)
    dropped = store.drop_inferences(s)
    store.add_event(s, "art21_objection", "profiling stopped")
    return jsonify(dict(envelope(s), rows_dropped=dropped))


@app.post("/api/rights/withdraw")
def r_withdraw():
    s = sid()
    store.set_consent(s, dict(store.DEFAULT_CONSENT, decided=True))
    store.set_session(s, withdrawn=1)
    dropped = store.drop_inferences(s)
    store.add_event(s, "art7_withdrawal", "consent withdrawn")
    return jsonify(dict(envelope(s), rows_dropped=dropped))


@app.post("/api/rights/rectify")
def r_rectify():
    s = sid()
    body = request.json or {}
    store.save_identity(s, {k: (body.get(k) or "")[:160] for k in ("name", "email")},
                        "corrected by you under Art. 16")
    store.add_event(s, "art16_rectification", "corrected")
    return jsonify(envelope(s))


@app.get("/api/rights/erase/plan")
def r_erase_plan():
    return jsonify({"steps": store.erasure_plan(), "counts": store.table_counts(sid())})


@app.post("/api/rights/erase/step")
def r_erase_step():
    s = sid()
    i = int((request.json or {}).get("index", 0))
    result = store.erase_step(s, i)
    result["counts"] = store.table_counts(s)
    if result.get("key") == "__finalise":
        result["envelope"] = envelope(s)
        # Drop the cookie too. There is no in-session memory of an erased subject:
        # reload the page and the server meets a stranger and starts collecting again.
        session.clear()
        result["session_cleared"] = True
    return jsonify(result)


@app.get("/api/rights/export.json")
def r_export():
    """Art. 20 — structured, commonly used, machine-readable."""
    s = sid()
    store.add_event(s, "art20_portability", "json export")
    payload = {
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "controller": "Panopti Ltd",
        "article": "GDPR Art. 20",
        "format": "application/json",
        "subject_id": (store.get_device(s)[0] or {}).get("fingerprintId"),
        "provided_by_you": {
            "identity": store.get_identity_multi(s),
            "identity_current": store.get_identity(s),
            "orders": [dict(o, items=json.loads(o["items"])) for o in store.get_orders(s)],
            "cart": store.get_cart(s),
            "wallet_links": store.get_wallet_links(s),
        },
        "observed_from_your_activity": {
            "device": store.get_device(s)[0],
            "telemetry": store.get_telemetry(s),
            "views": store.get_views(s),
            "searches": store.get_searches(s),
            "events": store.get_events(s),
            "signals": store.get_signals(s),
            "observation_log": store.get_observations(s, 2000),
        },
        "note": ("Derived inferences are excluded: Art. 20 covers data you provided and data "
                 "observed from your activity, not conclusions we drew. Those appear in full "
                 "in the Art. 15 pack, and you can have them deleted under Art. 21."),
    }
    r = make_response(json.dumps(payload, indent=2, default=str))
    r.headers["Content-Type"] = "application/json"
    r.headers["Content-Disposition"] = "attachment; filename=panopti-data-export.json"
    return r


@app.get("/api/rights/sar.pdf")
def r_sar():
    """Art. 15 — the readable pack."""
    from sar_pdf import build
    s = sid()
    store.add_event(s, "art15_access", "pdf generated")
    buf, ref = build(s)
    return send_file(buf, mimetype="application/pdf", as_attachment=True,
                     download_name="panopti-subject-access-%s.pdf" % ref)


@app.get("/api/rights/informed")
def r_informed():
    """Art. 13-14 — assembled live so it reflects what is actually happening."""
    s = sid()
    row = store.get_session(s) or {}
    c = store.get_consent(s)
    v = row.get("version", 1)
    restricted, stopped = bool(row.get("restricted")), bool(row.get("automated_stopped"))
    return jsonify({"sections": [
        {"t": "Who we are",
         "d": "Panopti Ltd, 4 Pocklington Yard, London EC1A 4XY. Data protection officer: "
              "dpo@panopti.example. You may complain to your regulator without telling us."},
        {"t": "Things you give us",
         "d": "Name, email, postal address and wallet address at the point you mint. Used to "
              "fulfil the order and to satisfy tax law, which is why six years of it survives "
              "a deletion request."},
        {"t": "Things your browser hands over",
         "d": "Device, browser, screen, language, timezone and rough location. Needed to draw "
              "the page and keep it secure, so this continues even under a restriction."},
        {"t": "Things we measure",
         "d": ("USER SELECTED PAUSE. The server is refusing telemetry, not hiding it."
               if restricted else
               ("Which collections and tokens you view, how long you dwell, what you search. "
                "Only because you switched analytics on." if (v == 2 and c.get("analytics"))
                else ("Everything, continuously, regardless of what you clicked." if v == 1
                      else "Nothing. You did not consent to analytics.")))},
        {"t": "Things we conclude",
         "d": ("USER SELECTED STOP. No inference runs and the inferences table is empty."
               if stopped else
               ("Age, gender, income, health and life events, derived rather than asked."
                if (v == 1 or (c.get("profiling") and not row.get("objected")))
                else "Nothing. No profile is being built about you."))},
        {"t": "Who else sees it",
         "d": ("Every partner we have, logged in the exports table as it happens." if v == 1
               else ("Two named partners." if c.get("share") else "Nobody outside Panopti."))},
        {"t": "How long we keep it",
         "d": "Six years for mint records because tax law requires it. Everything optional is "
              "shorter and listed in full in the panel on the right."},
        {"t": "Automated decisions",
         "d": ("USER SELECTED STOP." if stopped else
               "We order collections by predicted relevance and set fees from a risk tier. "
               "No legal effect, but you can still demand a human.")},
    ], "signals": {"restricted": restricted, "automated_stopped": stopped}})


# --------------------------------------------------------------------------
# advertising
# --------------------------------------------------------------------------
def _targeting_allowed(s):
    """Targeting dies the moment any relevant right is exercised."""
    row = store.get_session(s) or {}
    if row.get("erased"):
        return False, "erased"
    if row.get("restricted"):
        return False, PAUSE_SIGNAL
    if row.get("automated_stopped"):
        return False, STOP_SIGNAL
    if row.get("objected"):
        return False, "objected under Art. 21"
    c = store.get_consent(s)
    if row.get("version", 1) == 1:
        return True, "no permission sought"
    if row.get("withdrawn") or not c.get("ads"):
        return False, "no consent for advertising"
    return True, "consented under Art. 6(1)(a)"


def _ad_context(s):
    dev, _ip = store.get_device(s)
    return {"city": (dev or {}).get("city"), "browser": (dev or {}).get("browser"),
            "device": (dev or {}).get("deviceClass") or "device",
            "hour": time.localtime().tm_hour}


# Points are the gamification layer: you earn them, they are worth nothing, and
# the site earns real money for each one it hands out. That asymmetry is the
# point, so it is stated in the ledger rather than hidden.
PTS = {
    "ad impression seen": 1,
    "scrolled the catalogue": 2,
    "looked at a token": 3,
    "opened a token full size": 10,
    "searched": 6,
    "added to cart": 20,
    "ad conversion": 25,
    "completed a purchase": 120,
}

# Tiers exist to make the next one feel close. The gap widens each time, which
# is the oldest trick in loyalty design and worth seeing laid out honestly.
TIERS = [
    {"tier": "Bronze",   "at": 75,   "perk": "5% off any mint"},
    {"tier": "Silver",   "at": 250,  "perk": "10% off any mint"},
    {"tier": "Gold",     "at": 700,  "perk": "a free mint under $200"},
    {"tier": "Platinum", "at": 1800, "perk": "early access to every drop"},
]


def _award(s, reason, times=1):
    store.award_points(s, reason, PTS.get(reason, 0) * times)


def _rewards_payload(s):
    pts = store.points_total(s)
    redeemed = store.get_rewards(s)
    nxt = next((t for t in TIERS if pts < t["at"]), None)
    return {
        "points": pts,
        "tiers": [dict(t, unlocked=pts >= t["at"], redeemed=t["tier"] in redeemed)
                  for t in TIERS],
        "next": nxt,
        "goal": nxt["at"] if nxt else TIERS[-1]["at"],
        "next_tier": nxt["tier"] if nxt else "Platinum",
        "to_go": max(0, nxt["at"] - pts) if nxt else 0,
        "redeemed": redeemed,
        "rates": PTS,
    }


def _ad_payload(s):
    return dict(store.ad_summary(s), **_rewards_payload(s))


@app.get("/api/ad")
def api_ad():
    """One banner plus a slate of in-grid placements, all priced."""
    s = sid()
    allowed, why = _targeting_allowed(s)
    ctx = _ad_context(s)
    slate = []

    if allowed:
        counts = signal_counts(s)
        infs = compute_inferences(s, (store.get_session(s) or {}).get("version", 1))
        primary, score = ads.choose(counts, infs, ctx)
        for ad, sc in ads.pick_many(counts, infs, 16, ctx, exclude=(primary["id"],)):
            slate.append({"ad": ads.public(ad), "score": sc, "targeted": True})
        # grid placements first, banner last, so the ledger's "line item serving"
        # reports the ad the reader is actually looking at
        for slot in slate:
            store.add_ad_event(s, ads.BY_ID[slot["ad"]["id"]], "impression",
                               slot["ad"]["cpm"] / 1000.0, True)
        store.add_ad_event(s, primary, "impression", primary["cpm"] / 1000.0, True)
        _award(s, "ad impression seen", len(slate) + 1)
        store.record_signals(s, [("ad.shown", primary["advertiser"])])
        store.add_observation(s, "ad.shown",
                              narrate.render("ad.shown", "a %s ad" % primary["advertiser"],
                                             primary["why"])[0], 3)
    else:
        primary, score = ads.HOUSE, 0
        store.add_ad_event(s, primary, "impression", 0.0, False)
        store.record_signals(s, [("ad.blocked", why)])
        store.add_observation(s, "ad.blocked", narrate.render("ad.blocked")[0], 1)

    return jsonify({"ad": ads.public(primary), "targeted": allowed and primary["id"] != "house",
                    "reason": why, "score": score, "slate": slate,
                    "summary": _ad_payload(s)})


@app.post("/api/ad/click")
def api_ad_click():
    """A click is a conversion, and a conversion is the expensive kind of event."""
    s = sid()
    aid = (request.json or {}).get("id", "house")
    ad = ads.BY_ID.get(aid, ads.HOUSE)
    allowed, why = _targeting_allowed(s)
    targeted = allowed and ad["id"] != "house"
    rev = ad["cpc"] if targeted else 0.0
    store.add_ad_event(s, ad, "click", rev, targeted)
    if targeted:
        _award(s, "ad conversion")
    if targeted:
        store.add_observation(s, "ad.clicked",
                              narrate.render("ad.clicked", ad["advertiser"],
                                             "$%.2f" % rev)[0], 3)
    return jsonify(dict(envelope(s), summary=_ad_payload(s), revenue=rev,
                        points_awarded=PTS["ad conversion"] if targeted else 0,
                        advertiser=ad["advertiser"], reason=why))


@app.post("/api/rewards/redeem")
def api_redeem():
    s = sid()
    tier = (request.json or {}).get("tier", "")
    pts = store.points_total(s)
    match = next((t for t in TIERS if t["tier"] == tier), None)
    if not match:
        return jsonify({"error": "unknown tier"}), 400
    if pts < match["at"]:
        return jsonify({"error": "not enough points", "need": match["at"] - pts}), 400
    store.redeem(s, tier)
    store.add_event(s, "reward_redeemed", tier)
    store.add_observation(s, "reward.redeemed",
                          "Subject redeemed the %s reward. It cost us nothing and it "
                          "took %d engagement events to earn." % (tier, pts // 3), 3)
    return jsonify(dict(envelope(s), rewards=_rewards_payload(s), perk=match["perk"]))


@app.get("/api/rewards")
def api_rewards():
    return jsonify(_rewards_payload(sid()))


@app.get("/privacy")
def page_privacy():
    return _policy("privacy")


@app.get("/terms")
def page_terms():
    return _policy("terms")


def _policy(doc):
    """One template, two very different documents.

    v1 never names a recipient; v2 names every one, because Art. 13(1)(e) plus
    the EDPB transparency guidelines make naming the default and categories the
    exception that has to be justified.
    """
    s = sid()
    row = store.get_session(s) or {}
    version = int(row.get("version", 1))
    consent = store.get_consent(s)
    titles = {"privacy": "Privacy notice", "terms": "Terms of service"}

    if version == 1:
        sections = policy_text.V1_PRIVACY if doc == "privacy" else policy_text.V1_TERMS
    else:
        sections = [] if doc == "privacy" else policy_text.V2_TERMS

    return render_template(
        "policy.html", doc=doc, title=titles[doc], version=version,
        updated="14 March 2026" if version == 2 else "3 August 2019",
        sections=sections,
        purposes=policy_text.V2_PURPOSES,
        rights=policy_text.V2_RIGHTS,
        recipients=partners.for_consent(consent, version),
        advertiser_note=partners.ADVERTISER_NOTE,
    )


@app.get("/api/partners")
def api_partners():
    """Who is receiving anything right now, given the choices in force."""
    s = sid()
    row = store.get_session(s) or {}
    version = int(row.get("version", 1))
    consent = store.get_consent(s)
    live = partners.for_consent(consent, version)
    return jsonify({
        "version": version,
        "named": version == 2,
        "count": len(live),
        "recipients": [{k: r[k] for k in
                        ("name", "role", "sector", "location", "receives",
                         "purpose", "basis", "transfer", "retention", "shares")}
                       for r in live],
        "advertiser_note": partners.ADVERTISER_NOTE,
        "categories_only": None if version == 2 else partners.CATEGORY_FALLBACK,
    })


@app.get("/api/db")
def api_db():
    """Row counts, so the interface can show the database filling and emptying."""
    return jsonify(store.table_counts(sid()))


if __name__ == "__main__":
    # The tunnel comes up before the server so the banner can print both URLs
    # at once. use_reloader=False matters: with it on, Flask forks and ngrok
    # would be started twice, and the second one fails on the reserved domain.
    public = tunnel.start()
    tunnel.banner(public, os.path.abspath(store.DB_PATH))
    try:
        app.run(host=config.HOST, port=config.port(), debug=False, use_reloader=False)
    except KeyboardInterrupt:
        pass
    finally:
        tunnel.stop()
        print("\n  Stopped. Tunnel closed.\n")
