"""Profile construction.

Two switches change what happens here, and both stop work rather than hide it:

  restricted        (Art. 18)  -> optional observation is not ingested at all.
                                  Suppressed fields read "USER SELECTED PAUSE."
                                  Strictly necessary processing continues, and
                                  is labelled as such.

  automated_stopped (Art. 22)  -> no inference, no demographic guessing, and
                                  the inferences table is emptied. Every field
                                  reads "USER SELECTED STOP." so you can still
                                  see what we would have guessed.
"""
import hashlib
import time

import store
from catalog import PRODUCTS

PAUSE = "USER SELECTED PAUSE."
STOP = "USER SELECTED STOP."

BUYERS = ["Adzumi DSP", "NorthBeam Audiences", "Clearfield Identity Graph",
          "Pelham & Roe Analytics", "Marchetti Exchange", "Veridia Risk Signals",
          "OpenBid Consortium (1,284 vendors)", "Hollowtree Data Co-op"]

# fields the Art. 22 switch turns off, listed so the panel can show what is gone
AUTOMATED_FIELDS = [
    "estimated_age", "inferred_gender", "estimated_household_income",
    "household_composition", "homeowner_probability", "health_condition_probable",
    "mental_health_signal", "life_event_pregnancy", "life_event_bereavement",
    "financial_stress_index", "political_lean_modelled", "religion_cluster",
    "collector_sophistication", "attention_quality", "purchase_intent",
    "price_sensitivity", "interest_segments",
]


def h(s):
    return hashlib.sha256(str(s).encode()).hexdigest()


def mmss(seconds):
    s = int(seconds)
    return "%d min %02d s" % (s // 60, s % 60)


def inf(value, conf, **extra):
    d = {"value": value, "confidence": round(conf, 2)}
    d.update(extra)
    return d


# --------------------------------------------------------------------------
def signal_counts(sid):
    counts = {}
    for v in store.get_views(sid):
        p = PRODUCTS.get(v["token_id"])
        if not p:
            continue
        for s in p["sig"]:
            counts[s] = counts.get(s, 0) + v["views"]
    for c in store.get_cart(sid):
        p = PRODUCTS.get(c["token_id"])
        if p:
            for s in p["sig"]:
                counts[s] = counts.get(s, 0) + 3 * c["qty"]
    for q in store.get_searches(sid):
        if len(q) < 3:
            continue
        for p in PRODUCTS.values():
            if q.lower() in (p["n"] + " " + p["coll_name"]).lower():
                for s in p["sig"]:
                    counts[s] = counts.get(s, 0) + 2
    return counts


def compute_inferences(sid, version):
    """Derive everything. Callers must check automated_stopped before calling."""
    c = signal_counts(sid)
    dev, _ip = store.get_device(sid)
    o = {}
    cart = store.get_cart(sid)
    cart_value = sum(PRODUCTS[x["token_id"]]["p"] * x["qty"]
                     for x in cart if x["token_id"] in PRODUCTS)
    dwell_total = sum(v["dwell_ms"] for v in store.get_views(sid))
    orders = store.get_orders(sid)

    # v1 describes sensitivity commercially; v2 names the regulation
    def sc(label):
        return ({"special_category": "Art. 9 GDPR — " + label} if version == 2
                else {"tier": "premium segment — " + label})

    age, ac = 34, 0.41
    if "Windows 10" in (dev.get("os") or ""):
        age, ac = age + 4, ac
    if "Comic Sans MS" in (dev.get("fonts") or []):
        age += 6
    if c.get("retired"):
        age, ac = age + 18, ac + 0.12
    if c.get("kids"):
        age, ac = age - 4, ac + 0.06
    if c.get("pregnancy"):
        age, ac = age - 5, ac + 0.14
    if dev.get("deviceClass") == "smartphone":
        age -= 6
    if dev.get("darkMode"):
        age -= 3
    o["estimated_age"] = inf("%d ± 7" % max(18, min(78, round(age))), min(0.86, ac),
                             method="device cohort + collection affinity", never_asked=True)

    g, gc = "unresolved", 0.22
    if c.get("pregnancy"):
        g, gc = "female", 0.81
    elif c.get("craft") and c.get("home"):
        g, gc = "female (leaning)", 0.47
    elif c.get("hobby") and c.get("outdoor"):
        g, gc = "male (leaning)", 0.44
    o["inferred_gender"] = inf(g, gc, basis="purchase affinity model v11",
                               note="not self-declared")

    income, ic = "$55k–$80k", 0.38
    if c.get("financial", 0) >= 2:
        income, ic = "under $35k", 0.66
    elif c.get("budget", 0) >= 3:
        income, ic = "$28k–$48k", 0.58
    elif cart_value > 2000:
        income, ic = "$95k–$140k", 0.52
    o["estimated_household_income"] = inf(
        income, ic, signals_used=["cart value", "floor-price tier affinity",
                                  "device replacement cycle"])
    o["household_composition"] = inf(
        "adults with children under 12" if c.get("kids") else
        ("expecting first child" if c.get("pregnancy") else "1–2 adults, no children detected"),
        0.63 if (c.get("kids") or c.get("pregnancy")) else 0.29)
    o["homeowner_probability"] = inf(
        "likely owner" if c.get("home", 0) >= 3 else "likely renter", 0.34)

    if c.get("sleep", 0) >= 2:
        o["health_condition_probable"] = inf(
            "sleep disorder — insomnia or apnoea, untreated",
            min(0.88, 0.55 + c["sleep"] * 0.06),
            derived_from="collection affinity only; never disclosed by subject",
            onward_sale=["NorthBeam Audiences", "Adzumi DSP"], **sc("health data"))
    if c.get("anxiety", 0) >= 1:
        o["mental_health_signal"] = inf(
            "elevated anxiety indicators", min(0.72, 0.38 + c["anxiety"] * 0.06),
            derived_from="Support Rock and Liminal Carpet affinity + dwell pattern",
            used_for="creative rotation, bid multiplier", **sc("health data"))
    if c.get("pregnancy", 0) >= 1:
        o["life_event_pregnancy"] = inf(
            "first trimester, probable", 0.71,
            commercial_value="$4.19 CPM uplift — highest-value segment we hold",
            shared_before_disclosure_to_family=True, **sc("health data"))
    if c.get("grief", 0) >= 1:
        o["life_event_bereavement"] = inf(
            "recent death in immediate circle", 0.58, suppression_applied=False,
            used_for="memorial token and life insurance retargeting, 90 days")

    if c.get("financial", 0) >= 1 or c.get("budget", 0) >= 3:
        score = min(0.9, 0.35 + c.get("budget", 0) * 0.08 + c.get("financial", 0) * 0.12)
        o["financial_stress_index"] = inf(
            "%.2f / 1.00" % score, 0.61,
            used_for="dynamic fee markup, instalment eligibility, buyer risk tier",
            note="a higher score shows you a higher price, not a lower one")

    fp = dev.get("canvasFP") or "0"
    lean = "centre, low engagement"
    if dev.get("country") == "US":
        lean = ("centre-left, low engagement" if int(h(fp)[:2], 16) % 2
                else "centre-right, low engagement")
    o["political_lean_modelled"] = inf(
        lean, 0.31, basis="postal-code cluster + device cohort, no stated view",
        **sc("political opinions"))
    o["religion_cluster"] = inf("none observed / secular cluster", 0.19,
                                basis="minting seasonality", **sc("religious belief"))

    sess = store.get_session(sid) or {}
    o["collector_sophistication"] = inf(
        ("whale-adjacent, low diligence" if cart_value > 5000 else "retail, high enthusiasm")
        if sess.get("wallet") else "unconnected — browsing only",
        0.62 if sess.get("wallet") else 0.3,
        used_for="which floor price we show you first")
    o["attention_quality"] = inf(
        "high — engaged browser" if dwell_total > 9000 else
        ("moderate" if dwell_total > 3000 else "low / scanning"), 0.55,
        total_dwell_ms=round(dwell_total))
    o["purchase_intent"] = inf(
        ("converted" if orders else "high — cart held, not minted") if cart else
        ("browsing, warming" if len(store.get_views(sid)) > 3 else "cold"),
        0.74 if cart else 0.4,
        abandoned_cart_value=("$%s" % format(cart_value, ",")) if cart and not orders else None)
    o["price_sensitivity"] = inf(
        "high — shows low-floor collections first" if c.get("budget", 0) >= 2 else "standard",
        0.48)
    o["interest_segments"] = [
        {"segment": k, "strength": v,
         "iab_code": "IAB%d-%d" % (int(h(k)[:2], 16) % 23 + 1, int(h(k)[2:4], 16) % 9 + 1)}
        for k, v in sorted(c.items(), key=lambda kv: -kv[1])[:6]]
    return o


# --------------------------------------------------------------------------
def build_dossier(sid):
    sess = store.get_session(sid) or {}
    version = sess.get("version", 1)
    consent = store.get_consent(sid)
    restricted = bool(sess.get("restricted"))
    auto_stopped = bool(sess.get("automated_stopped"))
    objected = bool(sess.get("objected"))
    dev, ip = store.get_device(sid)
    ident = store.get_identity(sid)
    ident_multi = store.get_identity_multi(sid)
    tel = store.get_telemetry(sid)
    orders = store.get_orders(sid)
    elapsed = time.time() - (sess.get("created") or time.time())

    if sess.get("erased"):
        return {
            "erasure": {
                "status": "ERASED",
                "completed": time.strftime("%Y-%m-%d %H:%M:%S",
                                           time.localtime(sess.get("erased_at") or time.time())),
                "rows_remaining": store.table_counts(sid),
                "lawfully_retained": [
                    {"data": "mint invoices and tax records",
                     "basis": "Art. 17(3)(b) — legal obligation", "until": "6 years"},
                    {"data": "suppression hash",
                     "basis": "Art. 17 — to give effect to your erasure", "until": "indefinite"}],
                "downstream_confirmed": "all recipients notified under Art. 19",
            },
            "// note": ("these row counts come straight out of the database. "
                        "browse again and collection restarts from zero."),
        }

    collecting = True if version == 1 else (
        consent.get("decided") and (consent.get("analytics") or consent.get("ads")
                                    or consent.get("profiling")))
    profiling = True if version == 1 else (
        consent.get("decided") and consent.get("profiling") and not objected)
    profiling = profiling and not restricted and not auto_stopped

    out = {}

    # ---- identity -------------------------------------------------------
    # Nothing here is a single value. A field is a growing list, because that is
    # what a real profile looks like after someone has used three email addresses
    # and moved house twice.
    def vals(field):
        return [r["value"] for r in ident_multi.get(field, [])]

    names, emails, phones = vals("name"), vals("email"), vals("phone")
    total_values = sum(len(v) for v in ident_multi.values())
    name = (names[-1] if names else "").strip()

    out["identity"] = {
        "names_given": names or None,
        "given_name": name.split(" ")[0] if name else None,
        "family_name": " ".join(name.split(" ")[1:]) or None if name else None,
        "email_addresses": emails or None,
        "phone_numbers": phones or None,
        "postal_addresses": ([{"line1": r["value"], "city": (vals("city") or [None])[-1],
                               "postal_code": (vals("zip") or [None])[-1],
                               "country": dev.get("country")}
                              for r in ident_multi.get("addr1", [])] or None),
        "distinct_values_held": total_values,
        "how_each_was_captured": sorted({r["captured_by"] for rows in ident_multi.values()
                                         for r in rows}) or ["not yet supplied"],
        "persistent_id": dev.get("fingerprintId"),
        "cross_site_id": "CFG-" + h(name + (dev.get("canvasFP") or ""))[:12].upper(),
        "stored_in": "table `identity`, %d row%s" % (total_values,
                                                     "" if total_values == 1 else "s"),
    }
    if total_values > 1:
        out["identity"]["// retention"] = (
            "we keep every value you have ever entered, not just the current one. "
            "correcting a field adds a row; it does not replace one.")
    if version == 1 and not orders and any(
            r["captured_by"].startswith("keystroke") for rows in ident_multi.values()
            for r in rows):
        out["identity"]["// note"] = ("captured character-by-character as you typed and written "
                                      "to the database; you have not pressed any button")

    # ---- wallet ---------------------------------------------------------
    links = store.get_wallet_links(sid)
    if sess.get("wallet"):
        out["wallet_and_chain"] = {
            "custodial_wallet": sess["wallet"],
            "issued_by": "Panopti, automatically at checkout — you did not choose it",
            "chain": "Ethereum mainnet",
            "addresses_clustered": len(links) + 2 if version == 1 else len(links),
            "identity_linked": ("YES — wallet joined to %d name(s) and a postal address"
                                % len(names) if name else "pending — joins at checkout"),
            "lifetime_mints": len(orders),
            "stored_in": "table `wallet_links`",
            "// note": ("the wallet is pseudonymous. you are not. one postal address links "
                        "every address in the cluster, permanently." if version == 1 else
                        "kept against your order history only, never clustered."),
        }
    else:
        out["wallet_and_chain"] = {
            "custodial_wallet": None,
            "// note": "we issue one automatically at checkout. you are not asked."}

    # ---- device ---------------------------------------------------------
    dnt = dev.get("dnt") or dev.get("gpc")
    out["device_and_network"] = {
        "ip_address": ip,
        "approximate_location": "%s, %s%s" % (
            dev.get("city"), dev.get("country"),
            " (IP + timezone, accuracy ~2km)" if version == 1 else " (city level only)"),
        "timezone": dev.get("tz"), "utc_offset": dev.get("localTimeOffset"),
        "browser": dev.get("browser"), "operating_system": dev.get("os"),
        "user_agent": dev.get("ua"), "languages": dev.get("languages"),
        "screen": dev.get("screen"), "viewport": dev.get("viewport"),
        "pixel_ratio": dev.get("dpr"), "colour_depth": dev.get("colorDepth"),
        "cpu_cores": dev.get("cores"), "device_memory_gb": dev.get("memGB"),
        "touch_points": dev.get("touch"), "device_class": dev.get("deviceClass"),
        "gpu_renderer": dev.get("glRenderer"), "canvas_fingerprint": dev.get("canvasFP"),
        "installed_fonts_detected": dev.get("fonts") or ["(none detected)"],
        "prefers_dark_mode": dev.get("darkMode"), "connection": dev.get("conn"),
        "battery": dev.get("battery"), "referrer": dev.get("referrer"),
        "cookies_enabled": dev.get("cookiesEnabled"),
        "do_not_track": dev.get("dnt"), "global_privacy_control": dev.get("gpc"),
        "signal_response": (
            ("DETECTED — IGNORED. We are not obliged to act on it." if version == 1
             else "DETECTED — HONOURED. Treated as an objection under Art. 21(5).")
            if dnt else "no opt-out signal sent by this browser"),
        "retained_because": "strictly necessary — security, fraud and session integrity",
    }

    # ---- live tracking --------------------------------------------------
    if restricted:
        out["live_tracking"] = {
            "cursor_position": PAUSE,
            "cursor_travel_px": PAUSE,
            "cursor_speed_px_s": PAUSE,
            "movements_sampled": PAUSE,
            "clicks": PAUSE,
            "keystrokes": PAUSE,
            "time_on_page": mmss(elapsed),
            "session_heartbeat": "active — strictly necessary, continues during restriction",
            "// restriction": ("processing restricted under Art. 18. optional telemetry is no "
                               "longer accepted by the server, not merely hidden from you."),
        }
    else:
        out["live_tracking"] = {
            "cursor_position": "%s × %s" % (tel.get("x", 0), tel.get("y", 0)),
            "cursor_travel_px": round(tel.get("travel_px") or 0),
            "cursor_speed_px_s": round(tel.get("speed") or 0),
            "movements_sampled": tel.get("samples", 0),
            "clicks": tel.get("clicks", 0),
            "keystrokes": tel.get("keystrokes", 0),
            "time_on_page": mmss(elapsed),
            "// clock": "time on page refreshes once every 60 seconds; the cursor is continuous",
        }

    # ---- every signal the browser volunteered ---------------------------
    sig = store.get_signals(sid)
    if sig:
        groups = {}
        for key, row in sig.items():
            head = key.split(".")[0]
            groups.setdefault(head, {})[key.split(".", 1)[-1]] = (
                row["value"] if row["value"] not in ("", None)
                else ("seen %d\u00d7" % row["hits"] if row["hits"] > 1 else True))
        labels = {
            "dev": "hardware_and_browser", "mouse": "how_you_move",
            "click": "how_you_click", "key": "how_you_type",
            "win": "your_window", "visit": "when_you_came",
            "token": "what_caught_your_eye", "search": "what_you_looked_for",
            "form": "what_you_typed_into_forms", "cart": "what_you_nearly_bought",
            "sel": "what_you_selected", "coll": "what_you_kept_returning_to",
            "tab": "where_you_went", "pane": "what_you_tried_to_hide",
            "a11y": "accessibility_settings", "rights": "rights_you_used",
            "art18": "restriction", "art22": "automated_decisions",
        }
        volunteered = {}
        for head in sorted(groups):
            volunteered[labels.get(head, head)] = dict(sorted(groups[head].items()))
        volunteered["// count"] = ("%d distinct signals recorded, across %d categories. "
                                   "none of them were requested from you."
                                   % (len(sig), len(groups)))
        out["what_your_browser_volunteered"] = volunteered

    # ---- the activity log -------------------------------------------------
    # Milestones only. Every signal is still recorded, but a line is written
    # only when something is revealed or concluded, so the log stays readable.
    # Always present, even when empty, so it is open and waiting rather than
    # appearing out of nowhere once the first milestone lands.
    obs_n = store.count_observations(sid)
    entries = ["%s  %s" % (time.strftime("%H:%M:%S", time.localtime(r["ts"])), r["text"])
               for r in store.get_observations(sid, 30)]
    out["activity_log"] = {
        "entries": entries or ["waiting. move the pointer, or look at something."],
        "logged": obs_n,
        "showing": ("the %d most recent, newest first" % len(entries) if entries
                    else "nothing yet"),
        "written_by": "the server, in narrate.py — not by your browser",
        "// note": ("milestones only. routine movement is still recorded as a signal, "
                    "it just is not worth a sentence."),
    }

    # ---- the advertising ledger -------------------------------------------
    adsum = store.ad_summary(sid)
    if adsum["events"]:
        evs = store.get_ad_events(sid)
        imps = [e for e in evs if e["kind"] == "impression"]
        last = imps[-1] if imps else {}
        blocked = restricted or auto_stopped or objected or (
            version == 2 and not consent.get("ads"))
        reason = (PAUSE if restricted else STOP if auto_stopped
                  else "objected under Art. 21" if objected
                  else "no consent for advertising" if blocked else None)

        n_imp, n_conv = adsum["impressions"], adsum["clicks"]
        rev = adsum["revenue"]
        cvr = (n_conv / n_imp * 100) if n_imp else 0
        rpm = (rev / n_imp * 1000) if n_imp else 0
        pts_total = store.points_total(sid)

        # revenue split by which advertiser paid it
        by_adv = {}
        for e in evs:
            if e["revenue"]:
                by_adv[e["advertiser"]] = round(
                    by_adv.get(e["advertiser"], 0) + e["revenue"], 4)

        out["what_you_earned_us"] = {
            "line_item_serving": reason or last.get("advertiser"),
            "segment_you_were_sold_into": reason if blocked else last.get("segment"),
            "impressions": n_imp,
            "conversions": n_conv,
            "conversion_rate": "%.1f%%" % cvr,
            "gross_revenue": "$%.4f" % rev,
            "revenue_per_conversion": ("$%.2f" % (rev / n_conv)) if n_conv else "$0.00",
            "effective_cpm": "$%.2f" % rpm,
            "fill_rate": ("%.0f%%" % (adsum["targeted"] / n_imp * 100)) if n_imp else "0%",
            "paid_by": by_adv or "nobody",
            "targeting_status": reason or "active",
            "your_side_of_the_ledger": {
                "points_earned": pts_total,
                "points_cash_value": "$0.00",
                "earned_by": {b["reason"]: b["points"] for b in store.points_breakdown(sid)},
                "rewards_redeemed": store.get_rewards(sid) or "none",
                "transferable": False,
                "expire": "at the end of the session, like everything else you were promised",
            },
            "// note": ("you have earned %d points, worth $0.00. we have earned $%.4f, "
                        "worth $%.4f. every point we hand out is priced at nothing and "
                        "buys us another interaction." % (pts_total, rev, rev)),
        }

    # ---- behaviour ------------------------------------------------------
    if restricted:
        out["behaviour_this_session"] = {
            "status": PAUSE,
            "still_collected": {
                "cart_contents": [{"token": PRODUCTS[c["token_id"]]["n"], "qty": c["qty"]}
                                  for c in store.get_cart(sid) if c["token_id"] in PRODUCTS],
                "why": "strictly necessary to show you your own cart and complete a mint",
            },
            "no_longer_collected": ["page views", "dwell timing", "search terms",
                                    "scroll depth", "cursor telemetry", "tab focus"],
        }
    elif collecting:
        views = store.get_views(sid)
        out["behaviour_this_session"] = {
            "collections_browsed": sorted({PRODUCTS[v["token_id"]]["coll_name"]
                                           for v in views if v["token_id"] in PRODUCTS}),
            "tokens_viewed": [{"item": PRODUCTS[v["token_id"]]["n"],
                               "collection": PRODUCTS[v["token_id"]]["coll_name"],
                               "views": v["views"], "dwell_ms": round(v["dwell_ms"])}
                              for v in views if v["token_id"] in PRODUCTS],
            "searches": store.get_searches(sid) or None,
            "corrections_made": tel.get("backspaces", 0),
            "max_scroll_depth_pct": round(tel.get("scroll_max") or 0),
            "text_copied_times": tel.get("copies", 0),
            "tab_left_count": tel.get("blurs", 0),
            "time_away_from_tab_ms": round(tel.get("blur_ms") or 0),
            "rage_clicks": tel.get("rage", 0),
            "cart": [{"item": PRODUCTS[c["token_id"]]["n"], "qty": c["qty"],
                      "unit_price_usd": PRODUCTS[c["token_id"]]["p"]}
                     for c in store.get_cart(sid) if c["token_id"] in PRODUCTS],
            "cart_value_usd": sum(PRODUCTS[c["token_id"]]["p"] * c["qty"]
                                  for c in store.get_cart(sid) if c["token_id"] in PRODUCTS),
            "minted": bool(orders),
        }

    # ---- inference ------------------------------------------------------
    if auto_stopped:
        block = {"// status": (STOP + " Automated decision-making and profiling switched off "
                               "under Art. 22. The fields below are what we would otherwise "
                               "guess. Nothing is computed and the inferences table is empty.")}
        for k in AUTOMATED_FIELDS:
            block[k] = STOP
        block["rows_in_inference_table"] = len(store.get_inferences(sid))
        out["inferences_and_profiling"] = block
    elif restricted:
        out["inferences_and_profiling"] = {"// status": PAUSE +
                                           " Processing restricted under Art. 18."}
    elif profiling:
        derived = compute_inferences(sid, version)
        store.save_inferences(sid, derived)
        derived["rows_in_inference_table"] = len(store.get_inferences(sid))
        out["inferences_and_profiling"] = derived
    elif version == 2:
        out["inferences_and_profiling"] = {
            "// status": ("STOPPED — you objected under Art. 21. No profiles are derived."
                          if objected else
                          "not performed — you have not consented to profiling")}

    # ---- disclosure -----------------------------------------------------
    shared = BUYERS if version == 1 else (BUYERS[:2] if consent.get("share") else [])
    n_views = len(store.get_views(sid))
    worth = 0.19 + n_views * 0.31 + (1.4 if store.get_cart(sid) else 0)
    if not auto_stopped and not restricted and signal_counts(sid).get("pregnancy"):
        worth += 4.19
    out["who_has_bought_this"] = {
        "sold_to": shared or "no third parties",
        "transfers_logged": len(store.get_exports(sid)),
        "what_this_profile_is_worth": (
            "$%.2f" % worth if version == 1 else
            ("$0.38 (consented segments only)" if consent.get("share") else "$0.00")),
        "sent_abroad": ("yes — US and two others, contracts on file somewhere" if version == 1
                        else ("no — EEA only" if consent.get("share") else "none")),
    }

    # ---- basis and retention -------------------------------------------
    if version == 1:
        out["how_we_justify_this"] = {
            "the_banner": ("you clicked a button, so we say you agreed"
                           if consent.get("decided")
                           else "collection began before you decided anything"),
            "the_terms": "clause 3 says continued scrolling is agreement",
            "the_fallback": "where agreement is unclear we rely on our own commercial interests",
            "inferences": "derived by us, therefore ours, not yours",
            "opting_out": ("email privacy@panopti.example with two forms of certified "
                           "identification, allow 45 business days"),
        }
        out["retention"] = {"behaviour": "26 months", "profile": "indefinite",
                            "inferences": "indefinite", "wallet_cluster": "indefinite",
                            "backups": "7 years",
                            "deletion_on_request": "partial — derived data is retained"}
    else:
        out["consent_record"] = dict(consent, withdrawn=bool(sess.get("withdrawn")),
                                     withdrawal_mechanism="one button, effective immediately")
        out["retention"] = {
            "mint_and_invoice_records": "6 years — legal obligation, tax law",
            "analytics": "14 months, then aggregated beyond re-identification",
            "advertising_profile": "13 months" if consent.get("ads") else "not held",
            "inferences": "until you object, or 12 months" if profiling else "not held",
            "wallet_address": "kept against your order history only, never clustered",
            "backups": "30 day rolling, deletions replay on restore",
        }
        out["processing_status"] = {
            "restriction_art_18": PAUSE if restricted else "not restricted",
            "automated_decisions_art_22": STOP if auto_stopped else "active",
        }

    out["database"] = dict(store.table_counts(sid),
                           **{"// note": "live row counts from panopti.db"})
    return out
