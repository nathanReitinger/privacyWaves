"""The Article 15 subject access pack.

Written to be read by a person: every section opens with a plain-language
explanation of what the data is, where it came from and why we have it,
before any of the data itself appears.
"""
import io
import json
import sqlite3
import time

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph,
                                Spacer, Table, TableStyle, Flowable, PageBreak, KeepTogether)

import store
from catalog import PRODUCTS
from profiler import build_dossier, mmss, PAUSE, STOP

INK = colors.HexColor("#1b2430")
ACC = colors.HexColor("#1f5a7a")
SOFT = colors.HexColor("#5a6675")
FLAG = colors.HexColor("#9c2f3f")
RULE = colors.HexColor("#c2cad4")
BAND = colors.HexColor("#e8edf3")

PW, PH = A4
MARGIN = 20 * mm

S = {
    "h1": ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=15, leading=19,
                         textColor=INK, spaceAfter=3),
    "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=12.5, leading=16,
                         textColor=INK, spaceBefore=2, spaceAfter=5),
    "body": ParagraphStyle("body", fontName="Helvetica", fontSize=9.6, leading=13.6,
                           textColor=INK, alignment=TA_LEFT, spaceAfter=7),
    "expl": ParagraphStyle("expl", fontName="Helvetica-Oblique", fontSize=9.2, leading=13,
                           textColor=SOFT, spaceAfter=8),
    "small": ParagraphStyle("small", fontName="Helvetica", fontSize=8.2, leading=11,
                            textColor=SOFT, spaceAfter=4),
    "cell": ParagraphStyle("cell", fontName="Helvetica", fontSize=8.6, leading=11.4,
                           textColor=INK),
    "cellk": ParagraphStyle("cellk", fontName="Helvetica", fontSize=8.4, leading=11.2,
                            textColor=SOFT),
    "cellf": ParagraphStyle("cellf", fontName="Helvetica-Bold", fontSize=8.6, leading=11.4,
                            textColor=FLAG),
    "th": ParagraphStyle("th", fontName="Helvetica-Bold", fontSize=8.2, leading=10.5,
                         textColor=SOFT),
    "mono": ParagraphStyle("mono", fontName="Courier", fontSize=7.2, leading=9.2,
                           textColor=INK, spaceAfter=0),
    "boiler": ParagraphStyle("boiler", fontName="Helvetica", fontSize=8.4, leading=11.6,
                             textColor=SOFT, spaceAfter=6),
}


def esc(v):
    return (str(v).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


class Rule(Flowable):
    def __init__(self, w, color=RULE, thick=0.7):
        Flowable.__init__(self)
        self.w, self.color, self.thick = w, color, thick
        self.height = 1

    def wrap(self, *a):
        return self.w, self.thick + 6

    def draw(self):
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(self.thick)
        self.canv.line(0, 3, self.w, 3)


class SectionHead(Flowable):
    """A numbered heading with an accent bar, and a note on the right."""
    def __init__(self, w, title, note=""):
        Flowable.__init__(self)
        self.w, self.title, self.note = w, title, note

    def wrap(self, *a):
        return self.w, 30

    def draw(self):
        c = self.canv
        c.setFillColor(ACC)
        c.rect(0, 2, 3.2, 16, fill=1, stroke=0)
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 13)
        c.drawString(10, 6, self.title)
        if self.note:
            c.setFillColor(SOFT)
            c.setFont("Helvetica", 8.4)
            c.drawRightString(self.w, 6, self.note)


class ConfBar(Flowable):
    """One inference: label, confidence bar, percentage, and a note beneath."""
    def __init__(self, w, label, pct, note=""):
        Flowable.__init__(self)
        self.w, self.label, self.pct, self.note = w, label, max(0.0, min(1.0, pct)), note
        self._lines = []
        if note:
            words, line = note.split(), ""
            for wd in words:
                if len(line) + len(wd) + 1 > 118:
                    self._lines.append(line)
                    line = wd
                else:
                    line = (line + " " + wd).strip()
            if line:
                self._lines.append(line)

    def wrap(self, *a):
        return self.w, 15 + len(self._lines) * 9.6

    def draw(self):
        c = self.canv
        top = self.height if hasattr(self, "height") else 0
        y = 15 + len(self._lines) * 9.6 - 11
        c.setFillColor(INK)
        c.setFont("Helvetica", 9.2)
        label = self.label
        while c.stringWidth(label, "Helvetica", 9.2) > self.w - 105 and len(label) > 8:
            label = label[:-2]
        c.drawString(0, y, label)
        bx, bw = self.w - 88, 62
        c.setFillColor(colors.HexColor("#dbe0e7"))
        c.roundRect(bx, y - 1.5, bw, 8, 2, fill=1, stroke=0)
        c.setFillColor(FLAG if self.pct > 0.6 else ACC)
        c.roundRect(bx, y - 1.5, max(3, bw * self.pct), 8, 2, fill=1, stroke=0)
        c.setFillColor(SOFT)
        c.setFont("Helvetica", 7.6)
        c.drawRightString(self.w, y, "%d%%" % round(self.pct * 100))
        yy = y - 10
        c.setFont("Helvetica", 7.8)
        for ln in self._lines:
            c.drawString(9, yy, ln)
            yy -= 9.6


def kv_table(rows, width):
    """Two-column key/value table. A row may set flag=True to print in red."""
    data = []
    for k, v, *rest in rows:
        flag = rest[0] if rest else False
        if v is None or v == "":
            v = "not held"
        if isinstance(v, (list, tuple)):
            v = ", ".join(str(x) for x in v) or "none"
        style = S["cellf"] if flag else S["cell"]
        data.append([Paragraph(esc(k), S["cellk"]), Paragraph(esc(v), style)])
    t = Table(data, colWidths=[width * 0.33, width * 0.67])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("LINEBELOW", (0, 0), (-1, -2), 0.35, colors.HexColor("#e6eaef")),
    ]))
    return t


def grid_table(header, rows, width, weights):
    data = [[Paragraph(esc(h), S["th"]) for h in header]]
    for r in rows:
        data.append([Paragraph(esc(c), S["cell"]) for c in r])
    total = sum(weights)
    t = Table(data, colWidths=[width * w / total for w in weights], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BAND),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f7fa")]),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, RULE),
    ]))
    return t


# --------------------------------------------------------------------------
class Doc(BaseDocTemplate):
    def __init__(self, buf, ref):
        BaseDocTemplate.__init__(self, buf, pagesize=A4,
                                 leftMargin=MARGIN, rightMargin=MARGIN,
                                 topMargin=MARGIN, bottomMargin=MARGIN + 8 * mm,
                                 title="Subject access request", author="Panopti Ltd")
        self.ref = ref
        frame = Frame(MARGIN, MARGIN + 8 * mm, PW - 2 * MARGIN,
                      PH - 2 * MARGIN - 8 * mm, id="body")
        cover = Frame(MARGIN, MARGIN + 8 * mm, PW - 2 * MARGIN,
                      PH - 68 * mm - MARGIN, id="cover")
        self.addPageTemplates([
            PageTemplate(id="cover", frames=[cover], onPage=self._cover),
            PageTemplate(id="body", frames=[frame], onPage=self._chrome),
        ])

    def _chrome(self, c, doc):
        c.saveState()
        c.setStrokeColor(RULE)
        c.setLineWidth(0.6)
        c.line(MARGIN, MARGIN + 6 * mm, PW - MARGIN, MARGIN + 6 * mm)
        c.setFillColor(SOFT)
        c.setFont("Helvetica", 7.6)
        c.drawString(MARGIN, MARGIN + 2.2 * mm,
                     "Panopti Ltd   \u00b7   subject access request   \u00b7   " + self.ref)
        c.drawRightString(PW - MARGIN, MARGIN + 2.2 * mm, "page %d" % c.getPageNumber())
        c.restoreState()

    def _cover(self, c, doc):
        c.saveState()
        c.setFillColor(ACC)
        c.rect(0, PH - 58 * mm, PW, 58 * mm, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#c6d9e6"))
        c.setFont("Helvetica", 9.5)
        c.drawString(MARGIN, PH - 18 * mm, "PANOPTI LTD")
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 30)
        c.drawString(MARGIN, PH - 33 * mm, "Subject access")
        c.drawString(MARGIN, PH - 45 * mm, "request")
        c.setFillColor(colors.HexColor("#c6d9e6"))
        c.setFont("Helvetica", 10)
        c.drawString(MARGIN, PH - 52 * mm,
                     "Everything we hold about you, and what we did with it.")
        c.restoreState()
        self._chrome(c, doc)


# --------------------------------------------------------------------------
# ==========================================================================
# Appendices.
#
# These exist to make a point. A subject access request is answered in full,
# and "in full" from a company that collects this much is not a document any
# human being reads. Sections 1 to 10 are the useful part. Everything below is
# what completeness actually looks like: every row, every column, every
# partner, the same boilerplate restated for each one, and the raw record
# dumped verbatim at the end. It is all genuinely your data. That is the
# problem.
# ==========================================================================

SUBPROCESSORS = [
    ("Adzumi DSP", "Ireland", "real-time bidding", "SCCs 2021/914, module two"),
    ("NorthBeam Audiences", "United States", "audience segments", "SCCs + supplementary measures"),
    ("Clearfield Identity Graph", "United States", "identity resolution", "SCCs 2021/914"),
    ("Pelham & Roe Analytics", "United Kingdom", "measurement", "UK adequacy"),
    ("Marchetti Exchange", "Netherlands", "supply-side platform", "EEA, no transfer"),
    ("Veridia Risk Signals", "Singapore", "fraud scoring", "SCCs 2021/914"),
    ("OpenBid Consortium", "various (1,284 vendors)", "programmatic auction", "per-vendor terms"),
    ("Hollowtree Data Co-op", "United States", "data enrichment", "SCCs 2021/914"),
    ("Sandmere Hosting", "Ireland", "infrastructure", "EEA, no transfer"),
    ("Quillon Mail Relay", "Germany", "transactional email", "EEA, no transfer"),
    ("Brackwater Logs", "United States", "log aggregation", "SCCs 2021/914"),
    ("Tessellate CDN", "global edge", "content delivery", "SCCs 2021/914"),
]

GLOSSARY = [
    ("Canvas fingerprint", "A hash of how your graphics hardware draws a fixed test image. "
     "Two devices of the same model usually differ. You cannot clear it."),
    ("Controller", "The organisation deciding why and how your data is processed. Here, us."),
    ("Cross-site identifier", "An identifier designed to recognise you on sites other than "
     "this one."),
    ("Data subject", "You."),
    ("Dwell", "How long your cursor rested on something without clicking it."),
    ("Derived data", "A conclusion we reached rather than a fact you gave us. Still your "
     "personal data, whatever our terms of service claim."),
    ("Fingerprint", "A stable identifier assembled from characteristics your browser "
     "discloses automatically. Survives clearing cookies."),
    ("Inference", "A guess, expressed as a probability, acted on as though it were a fact."),
    ("Legitimate interest", "A lawful basis that does not require your agreement, subject to "
     "a balancing test we perform on ourselves."),
    ("Processor", "A company processing your data on our instructions."),
    ("Profiling", "Automated processing to evaluate things about you, such as health, "
     "finances, interests or behaviour."),
    ("Rage click", "Three or more clicks in the same place in under a second. Read as "
     "frustration."),
    ("Restriction", "Storage without use. Your data stays; the processing stops."),
    ("Segment", "A bucket we put you in so it can be sold by the thousand."),
    ("Special category data", "Health, beliefs, politics, sex life, ethnicity, biometrics, "
     "union membership. Inferred counts."),
    ("Suppression hash", "A one-way hash kept after erasure, so we can recognise that we "
     "must not build a profile of you again."),
    ("Telemetry", "Measurements of how you moved, scrolled, typed and hesitated."),
]

TERMS = [
    ("1. Acceptance", "By loading, rendering or caching this Service you enter a binding "
     "agreement with Panopti Ltd, its successors, affiliates and any entity acquiring "
     "substantially all of its assets. Data collected before you stop using it is retained "
     "under clause 14."),
    ("2. Definitions", "\u201cYour Data\u201d means data relating to you. \u201cOur Data\u201d "
     "means any conclusion, score, probability, segment or prediction we generate from it, "
     "and is our intellectual property rather than yours."),
    ("3. Agreement", "Agreement is taken as given by continued use, by scrolling, by "
     "dismissing any notice, by inaction following notice, or by closing a notice by any "
     "means including the close control."),
    ("4. Collection", "We collect identifiers, device and network characteristics, "
     "behavioural telemetry, interaction timing, input cadence, cursor kinematics, wallet "
     "addresses and clusters, and any content entered into any field whether or not that "
     "field is subsequently submitted."),
    ("5. Our interests", "Where agreement is withheld or found ineffective we continue "
     "processing on the basis of our own commercial interests, assessed internally and "
     "found to outweigh yours. That assessment is confidential."),
    ("6. Partners", "We disclose Your Data and Our Data to our partners, each applying its "
     "own notice which you are taken to have read."),
    ("7. Sensitive inferences", "Where Our Data concerns your health, sleep, mental state, "
     "family circumstances, finances, beliefs or opinions, you agree to that processing by "
     "continuing to use the Service."),
    ("8. Automated pricing", "Prices, fees, offers and support routing may be set by "
     "automated means including profiling. Outcomes may differ between users viewing "
     "identical tokens."),
    ("9. Information requests", "Requests must be made in writing by post with two forms of "
     "certified identification and, where the request concerns Our Data, a reasoned "
     "explanation of why disclosure would not prejudice our commercial interests."),
    ("10. Retention", "We retain Your Data for twenty-six months. Our Data, aggregated data, "
     "pseudonymised data, backups and partner copies fall outside that period."),
    ("11. Transfer", "Data is transferred to jurisdictions which may not protect it to the "
     "same standard. You agree to that transfer and waive, so far as permitted, any claim "
     "arising from it."),
    ("12. Changes", "We may vary these terms at any time without notice. The version in "
     "force is the one displayed at your most recent interaction, which may differ from the "
     "version you read."),
    ("13. Waiver", "You waive any right to participate in a class, collective or "
     "representative action."),
    ("14. Deletion", "On a verified request we delete Your Data from our primary production "
     "database. Our Data, analytical copies, partner copies, backups, wallet clusters and "
     "training corpora are excluded from this undertaking."),
    ("15. Severability", "If any clause is unenforceable the remainder survives, and that "
     "clause is read down to the maximum extent permitted rather than struck."),
]

RIGHTS_RESTATED = [
    ("Right to be informed", "Art. 13\u201314",
     "you are entitled to know what is collected and why, at the time it happens."),
    ("Right of access", "Art. 15",
     "you may request a copy of everything held, free, within one month."),
    ("Right to rectification", "Art. 16",
     "inaccurate or incomplete records are corrected and recipients are told."),
    ("Right to erasure", "Art. 17",
     "records are deleted unless a legal obligation requires us to keep them."),
    ("Right to restrict processing", "Art. 18",
     "we keep the records but stop using them while a dispute is resolved."),
    ("Right to data portability", "Art. 20",
     "you may take a machine-readable copy to another service."),
    ("Right to object", "Art. 21",
     "you may tell us to stop; for direct marketing there is no balancing test."),
    ("Automated decisions", "Art. 22",
     "a person reviews the outcome instead of an algorithm deciding alone."),
    ("Withdraw consent", "Art. 7(3)",
     "withdrawal must be as easy as consent was to give."),
    ("Complain", "Art. 77",
     "you may go to your supervisory authority without contacting us first."),
]

RETENTION_NOTES = {
    "sessions": "Session state and your recorded choices. 26 months.",
    "identity": "Every name, email, phone and address value ever entered. 6 years where "
                "attached to an order, otherwise 26 months.",
    "device": "Device and network fingerprint. 26 months.",
    "telemetry": "Cursor, scroll, typing and attention measurements. 14 months.",
    "views": "Which tokens you looked at and for how long. 14 months.",
    "searches": "Search terms, including ones that returned nothing. 14 months.",
    "cart": "Items queued but not bought. 26 months, because abandonment is valuable.",
    "orders": "Invoices. 6 years, legal obligation, survives erasure.",
    "events": "The event stream. 26 months.",
    "inferences": "Conclusions drawn about you. Indefinite in v1, 12 months in v2.",
    "wallet_links": "Wallet addresses joined to names. Indefinite in v1.",
    "exports": "Record of each onward transfer. 6 years.",
    "suppression": "Post-erasure suppression hashes. Indefinite, by design.",
}


def _schema_columns():
    """Read the real schema, so the retention table cannot drift from the code."""
    out = []
    try:
        con = sqlite3.connect(store.DB_PATH)
        con.row_factory = sqlite3.Row
        for t in con.execute("SELECT name FROM sqlite_master WHERE type='table' "
                             "AND name NOT LIKE 'sqlite_%' ORDER BY name"):
            tbl = t["name"]
            cols = [r["name"] for r in con.execute("PRAGMA table_info(%s)" % tbl)]
            out.append((tbl, cols))
        con.close()
    except Exception:
        pass
    return out


def _appendices(f, sid, d, W, head, para, ref, version):
    """Everything a maximally literal reading of Article 15 produces."""
    events = store.get_events(sid)
    views = store.get_views(sid)
    searches = store.get_searches(sid)
    ident_multi = store.get_identity_multi(sid)
    exports = store.get_exports(sid)
    orders = store.get_orders(sid)
    dev, ip = store.get_device(sid)

    f.append(PageBreak())
    head("Appendices", "the complete record")
    para("What follows is the rest of your data, in full, because that is what you asked "
         "for and what the law entitles you to. It is also, deliberately, unreadable at "
         "length. Sections 1 to 10 above are the part you can act on. Everything from here "
         "is every row we hold, every partner restated in identical language, the schema "
         "column by column, and finally the raw record verbatim.", "body")
    para("We are not padding this to hide anything. We are showing you that a complete "
         "answer, from a company that collects at this volume, is itself a way of telling "
         "you nothing. A pack you cannot finish is a pack you cannot check. Bear that in "
         "mind when a real company sends you four hundred pages.", "expl")
    f.append(Rule(W))
    for line in ["A   Every event, in order",
                 "B   Every value each field has ever held",
                 "C   Token-by-token viewing history",
                 "D   Search history, verbatim",
                 "E   Device record, field by field",
                 "F   Recipient register, one entry per recipient",
                 "G   Sub-processors and transfer mechanisms",
                 "H   Retention schedule, table by table, column by column",
                 "I   Record of processing activities, extract",
                 "J   Glossary of every term used in this pack",
                 "K   Your order history, itemised",
                 "L   The raw record, verbatim",
                 "M   Terms you accepted, reproduced in full",
                 "N   Your rights, restated for each category of data we hold",
                 "O   Cookie and identifier register",
                 "P   Document control",
                 "Q   Every signal your browser volunteered",
                 "R   The narrated observation log, in full"]:
        para(line, "small")

    # ---- A: event log -------------------------------------------------
    f.append(PageBreak())
    head("Appendix A   Every event, in order", "%d rows" % len(events))
    para("One row per thing you did. Timestamps are server time.", "expl")
    if events:
        rows = [(time.strftime("%H:%M:%S", time.localtime(e["ts"])),
                 e["type"], e["detail"] or "") for e in events]
        for i in range(0, len(rows), 34):
            f.append(grid_table(["Time", "Event", "Detail"], rows[i:i + 34], W, [16, 30, 54]))
            if i + 34 < len(rows):
                f.append(PageBreak())
    else:
        para("No events recorded.", "small")

    # ---- B: identity provenance ---------------------------------------
    f.append(PageBreak())
    head("Appendix B   Every value each field has ever held",
         "%d rows" % sum(len(v) for v in ident_multi.values()))
    para("We do not overwrite. A correction adds a row; the earlier value stays. This is "
         "the complete history of every field, including values you typed and then changed "
         "your mind about.", "expl")
    rows = []
    for field in sorted(ident_multi):
        for r in ident_multi[field]:
            rows.append((field, r["value"], r["captured_by"],
                         time.strftime("%H:%M:%S", time.localtime(r["first_seen"]))))
    if rows:
        f.append(grid_table(["Field", "Value", "How we got it", "First seen"],
                            rows, W, [16, 32, 36, 16]))
    else:
        para("No identity values held.", "small")

    # ---- C: viewing history -------------------------------------------
    f.append(PageBreak())
    head("Appendix C   Token-by-token viewing history", "%d rows" % len(views))
    para("Every token you rested on, how many times, and for how long in milliseconds.",
         "expl")
    if views:
        rows = [(PRODUCTS.get(v["token_id"], {}).get("n", v["token_id"]),
                 PRODUCTS.get(v["token_id"], {}).get("coll_name", "\u2014"),
                 str(v["views"]), "%d ms" % round(v["dwell_ms"])) for v in views]
        f.append(grid_table(["Token", "Collection", "Views", "Dwell"], rows, W, [36, 32, 12, 20]))
    else:
        para("No viewing history held.", "small")

    # ---- D: searches ---------------------------------------------------
    f.append(PageBreak())
    head("Appendix D   Search history, verbatim", "%d rows" % len(searches))
    para("Including searches that returned nothing, which are often the most revealing.",
         "expl")
    if searches:
        srows = []
        for q in searches:
            if isinstance(q, dict):
                srows.append((time.strftime("%H:%M:%S", time.localtime(q.get("ts", 0))),
                              q.get("q", "")))
            else:
                srows.append(("\u2014", str(q)))
        f.append(grid_table(["Time", "Query"], srows, W, [20, 80]))
    else:
        para("No searches recorded.", "small")

    # ---- E: device record ----------------------------------------------
    f.append(PageBreak())
    head("Appendix E   Device record, field by field", "as disclosed by your browser")
    para("None of this was requested from you. Your browser volunteers it to every site "
         "you visit; we simply wrote it down.", "expl")
    drows = [("ip_address", ip or "not recorded")]
    for k in sorted(dev or {}):
        v = dev[k]
        if isinstance(v, (list, dict)):
            v = json.dumps(v)
        drows.append((k, str(v)))
    f.append(grid_table(["Attribute", "Value"], drows, W, [30, 70]))

    # ---- F: recipient register -----------------------------------------
    f.append(PageBreak())
    head("Appendix F   Recipient register", "%d transfer%s logged"
         % (len(exports), "" if len(exports) == 1 else "s"))
    para("Article 15(1)(c) entitles you to the recipients. Each one gets its own entry. "
         "The wording is identical every time because the arrangement is identical every "
         "time, which is itself worth noticing.", "expl")
    if exports:
        for n, e in enumerate(exports, 1):
            if n > 1:
                f.append(PageBreak())
            f.append(KeepTogether([
                Paragraph("F.%d&nbsp;&nbsp;%s" % (n, esc(e["recipient"])), S["h2"]),
                kv_table([
                    ("Transferred at", time.strftime("%d %B %Y, %H:%M:%S",
                                                     time.localtime(e["ts"]))),
                    ("Categories transferred", e["summary"]),
                    ("Lawful basis asserted",
                     "your agreement to the notice" if version == 1 else "your consent"),
                    ("Onward transfer permitted", "yes" if version == 1 else "no"),
                    ("Retention at recipient", "governed by their own notice, not ours"),
                    ("Deletion on your request",
                     "we notify them under Art. 19; enforcement is between you and them"),
                    ("Contact", "see their published privacy notice"),
                ], W),
                Spacer(1, 6),
            ]))
    else:
        para("No transfers logged for you.", "small")

    # ---- G: sub-processors ----------------------------------------------
    f.append(PageBreak())
    head("Appendix G   Sub-processors and transfer mechanisms", "standing list")
    para("Everyone who may touch your data in the course of us running this service, "
         "whether or not anything of yours actually reached them.", "expl")
    f.append(grid_table(["Sub-processor", "Location", "Purpose", "Transfer mechanism"],
                        SUBPROCESSORS, W, [26, 22, 26, 26]))
    f.append(Spacer(1, 8))
    para("For each entry above the following applies, restated in full as required:", "small")
    for nm, loc, purpose, mech in SUBPROCESSORS:
        f.append(KeepTogether([
            Paragraph("<b>%s</b>" % esc(nm), S["small"]),
            Paragraph("%s processes personal data in %s for the purpose of %s. The transfer "
                      "mechanism relied upon is %s. A copy of the relevant agreement is "
                      "available on request, subject to redaction of commercially sensitive "
                      "terms. %s is contractually required to implement appropriate technical "
                      "and organisational measures and to assist us in responding to requests "
                      "such as this one. Where %s engages its own sub-processors, it remains "
                      "responsible to us for their performance."
                      % (esc(nm), esc(loc), esc(purpose), esc(mech), esc(nm), esc(nm)),
                      S["boiler"]),
        ]))

    # ---- H: retention schedule -------------------------------------------
    f.append(PageBreak())
    head("Appendix H   Retention schedule, table by table, column by column",
         "read from the live schema")
    para("The tables below are the actual tables in the database, read at the moment this "
         "pack was generated. Nothing here is a description of our intentions; it is the "
         "schema.", "expl")
    for tbl, cols in _schema_columns():
        f.append(KeepTogether([
            Paragraph("<b>%s</b>" % esc(tbl), S["h2"]),
            Paragraph(esc(RETENTION_NOTES.get(tbl, "Operational table. 26 months.")),
                      S["small"]),
            grid_table(["Column", "Holds", "Retention"],
                       [(c, "personal data" if tbl != "suppression" else "pseudonymised hash",
                         RETENTION_NOTES.get(tbl, "26 months").split(". ")[-1])
                        for c in cols], W, [26, 34, 40]),
            Spacer(1, 6),
        ]))

    # ---- I: ROPA ----------------------------------------------------------
    f.append(PageBreak())
    head("Appendix I   Record of processing activities, extract", "Art. 30")
    para("Our internal processing register, filtered to activities that touched you.",
         "expl")
    ropa = [
        ("Marketplace delivery", "Art. 6(1)(b)", "device, session", "26 months", "none"),
        ("Order fulfilment", "Art. 6(1)(b)", "identity, orders", "6 years", "payment, delivery"),
        ("Fraud prevention", "Art. 6(1)(f)", "device, telemetry", "26 months", "Veridia"),
        ("Service analytics", "Art. 6(1)(a)", "views, searches", "14 months", "Pelham & Roe"),
        ("Audience building", "Art. 6(1)(a)", "inferences", "13 months", "NorthBeam, Adzumi"),
        ("Identity resolution", "Art. 6(1)(f)", "fingerprint, wallet", "indefinite", "Clearfield"),
        ("Model training", "Art. 6(1)(f)", "all behavioural", "indefinite", "none"),
        ("Rights handling", "Art. 6(1)(c)", "identity, events", "6 years", "none"),
    ]
    f.append(grid_table(["Activity", "Basis", "Categories", "Retention", "Recipients"],
                        ropa, W, [24, 16, 22, 16, 22]))

    # ---- J: glossary -------------------------------------------------------
    f.append(PageBreak())
    head("Appendix J   Glossary", "every term used in this pack")
    para("Defined so that the pack is self-contained, which is also how a pack becomes "
         "long enough that nobody reaches the end.", "expl")
    for term, defn in GLOSSARY:
        f.append(KeepTogether([
            Paragraph("<b>%s</b>" % esc(term), S["small"]),
            Paragraph(esc(defn), S["boiler"]),
        ]))

    # ---- K: orders ----------------------------------------------------------
    f.append(PageBreak())
    head("Appendix K   Your order history, itemised", "%d order%s"
         % (len(orders), "" if len(orders) == 1 else "s"))
    para("Retained for six years under tax law. This is the part an erasure request cannot "
         "remove, and we would rather say so plainly than let you discover it later.",
         "expl")
    if orders:
        for o in orders:
            try:
                items = json.loads(o["items"])
            except Exception:
                items = []
            f.append(KeepTogether([
                Paragraph("<b>Order #%s</b>&nbsp;&nbsp;<font size=7.5 color='#5a6675'>%s</font>"
                          % (o["id"], time.strftime("%d %B %Y, %H:%M",
                                                    time.localtime(o["ts"]))), S["body"]),
                grid_table(["Token", "Digest", "Qty", "Price"],
                           [(i.get("token", ""), "#" + str(i.get("hash", "")),
                             str(i.get("qty", 1)), "$%s" % format(i.get("usd", 0), ","))
                            for i in items], W, [40, 24, 12, 24]),
                Spacer(1, 6),
            ]))
    else:
        para("No orders placed.", "small")

    # ---- L: raw dump ---------------------------------------------------------
    f.append(PageBreak())
    head("Appendix L   The raw record, verbatim", "no formatting applied")
    para("The profile exactly as the server holds it. Included because a summary is a "
         "choice about what to leave out, and you did not ask us to choose.", "expl")
    raw = json.dumps(d, indent=2, default=str, ensure_ascii=False)
    for line in raw.split("\n"):
        line = line.rstrip()
        if len(line) > 118:
            line = line[:118] + " \u2026"
        f.append(Paragraph(esc(line).replace(" ", "&nbsp;") or "&nbsp;", S["mono"]))

    # ---- M: the terms, reproduced -------------------------------------------
    f.append(PageBreak())
    head("Appendix M   Terms you accepted, reproduced in full", "15 of 47 sections")
    para("Reproduced because you are entitled to know what we say we may do. Sections 16 "
         "to 47 are available on request, which is the sort of sentence that ends most "
         "people\u2019s curiosity.", "expl")
    for title, body in TERMS:
        f.append(KeepTogether([
            Paragraph("<b>%s</b>" % esc(title), S["small"]),
            Paragraph(esc(body), S["boiler"]),
        ]))

    # ---- N: rights restated per category ------------------------------------
    f.append(PageBreak())
    head("Appendix N   Your rights, restated for each category of data we hold",
         "%d categories" % len(RETENTION_NOTES))
    para("Article 15 requires us to tell you about your rights. Rather than say it once, "
         "we say it for every table, because nobody has ever been fined for answering at "
         "excessive length.", "expl")
    for tbl in sorted(RETENTION_NOTES):
        f.append(PageBreak())
        f.append(Paragraph("N.%s&nbsp;&nbsp;Category: <b>%s</b>"
                           % (tbl[:3], esc(tbl)), S["h2"]))
        f.append(Paragraph(esc(RETENTION_NOTES[tbl]), S["small"]))
        f.append(Spacer(1, 4))
        for title, art, text in RIGHTS_RESTATED:
            f.append(Paragraph(
                "<b>%s</b>&nbsp;&nbsp;<font size=7.5 color='#5a6675'>%s</font>&nbsp;&nbsp;"
                "In relation to the <b>%s</b> category: %s"
                % (esc(title), esc(art), esc(tbl), esc(text)), S["boiler"]))

    # ---- O: cookie and identifier register ----------------------------------
    f.append(PageBreak())
    head("Appendix O   Cookie and identifier register", "what recognises you")
    para("Not all of these are cookies, which is why clearing cookies does less than "
         "people expect.", "expl")
    f.append(grid_table(
        ["Identifier", "Type", "Set by", "Lifetime", "Cleared by you?"],
        [("session", "HTTP cookie", "Panopti", "browser session", "yes, on request"),
         ("device fingerprint", "derived", "Panopti", "permanent", "no"),
         ("canvas hash", "derived", "Panopti", "permanent", "no"),
         ("font enumeration", "derived", "Panopti", "permanent", "no"),
         ("cross-site id", "derived", "Panopti", "permanent", "no"),
         ("custodial wallet", "account identifier", "Panopti", "indefinite", "no"),
         ("IP address", "network", "your connection", "per session", "only via VPN"),
         ("UA string", "network", "your browser", "per request", "no")],
        W, [24, 18, 16, 20, 22]))

    # ---- P: document control --------------------------------------------------
    f.append(PageBreak())
    head("Appendix P   Document control", ref)
    f.append(kv_table([
        ("Reference", ref),
        ("Generated", time.strftime("%d %B %Y at %H:%M:%S")),
        ("Generated by", "automated pipeline, no human reviewed this pack"),
        ("Source", "panopti.db, read at generation time"),
        ("Template version", "SAR-TPL-4.2"),
        ("Pages", "see the footer of the final page"),
        ("Format", "PDF/A not asserted"),
        ("Accessibility", "not tagged for screen readers"),
        ("Language", "English only"),
        ("Redactions applied", "none"),
        ("Review status", "not reviewed"),
        ("Retention of this pack", "6 years, alongside the request that produced it"),
    ], W))
    para("That last row is worth a second look. Asking us what we hold about you creates "
         "a new record about you, which we then hold for six years.", "expl")

    # ---- Q: raw signals ------------------------------------------------------
    sigs = store.get_signals(sid)
    f.append(PageBreak())
    head("Appendix Q   Every signal your browser volunteered", "%d signals" % len(sigs))
    para("Not one of these was requested from you, and not one of them required a "
         "permission prompt. They are simply what a web page can read about a visitor "
         "who arrives and moves a pointer.", "expl")
    if sigs:
        rows = [(k, sigs[k]["value"] or "\u2014", str(sigs[k]["hits"]),
                 time.strftime("%H:%M:%S", time.localtime(sigs[k]["first_seen"])))
                for k in sorted(sigs)]
        for i in range(0, len(rows), 32):
            f.append(grid_table(["Signal", "Value", "Seen", "First"],
                                rows[i:i + 32], W, [28, 46, 10, 16]))
            if i + 32 < len(rows):
                f.append(PageBreak())
    else:
        para("No signals recorded.", "small")

    # ---- R: the narration ------------------------------------------------------
    obs = store.get_observations(sid, 4000)
    f.append(PageBreak())
    head("Appendix R   The narrated observation log, in full", "%d entries" % len(obs))
    para("The sentences below were written by the server as you browsed, one for each "
         "signal the first time it appeared. They are the plain-English version of "
         "Appendix Q, and they are what the panel showed you in real time.", "expl")
    para("Reading them in sequence is the closest thing to seeing yourself the way the "
         "server does. It is worth the two minutes, and it is the only part of these "
         "appendices we would actually recommend.", "expl")
    if obs:
        rows = [(time.strftime("%H:%M:%S", time.localtime(r["ts"])),
                 ("routine", "behaviour", "device", "inference")[min(3, r["tier"])],
                 r["text"]) for r in reversed(obs)]
        for i in range(0, len(rows), 26):
            f.append(grid_table(["Time", "Kind", "What the server said about you"],
                                rows[i:i + 26], W, [14, 16, 70]))
            if i + 26 < len(rows):
                f.append(PageBreak())
    else:
        para("Nothing observed.", "small")

    f.append(PageBreak())
    head("End of pack", ref)
    para("If you read this far, you did something almost nobody does, and you now know more "
         "about what this service holds on you than most people will ever know about any "
         "service they use.", "body")
    para("The useful version of this document is the JSON export under Article 20, which a "
         "machine can read in a second. The useful version of this right is the one you "
         "exercise before the data exists.", "expl")


def build(sid):
    d = build_dossier(sid)
    sess = store.get_session(sid) or {}
    version = sess.get("version", 1)
    ident = store.get_identity(sid)
    name = (ident.get("name") or "").strip()
    ref = "SAR-%s-%s" % (time.strftime("%Y"), format(abs(hash(sid)) % 0xFFFFFF, "06X"))
    deadline = time.strftime("%d %B %Y", time.localtime(time.time() + 30 * 86400))

    buf = io.BytesIO()
    doc = Doc(buf, ref)
    W = PW - 2 * MARGIN
    f = []

    def head(title, note=""):
        f.append(SectionHead(W, title, note))

    def para(t, style="body"):
        f.append(Paragraph(t, S[style]))

    # ---------------- cover ----------------
    para("Prepared for %s" % (name or "the person identified below"), "h1")
    para("This document answers your request under Article 15 of the General Data Protection "
         "Regulation. Every section starts by explaining, in plain words, what the data is, "
         "where it came from and why we hold it. The data itself follows. Nothing here is "
         "summarised or rounded off to make us look better.")
    f.append(Rule(W))
    f.append(kv_table([
        ("Reference", ref),
        ("Issued", time.strftime("%d %B %Y, %H:%M")),
        ("Response deadline", "%s  (one month, Art. 12(3))" % deadline),
        ("Fee", "\u00a30.00 \u2014 no charge may be made for a first request"),
        ("Person", name or "identified by device fingerprint only"),
        ("Subject identifier", d.get("identity", {}).get("persistent_id") or "not yet derived"),
        ("Wallet on file", sess.get("wallet") or "none connected"),
        ("Controller", "Panopti Ltd, 4 Pocklington Yard, London EC1A 4XY"),
        ("Data protection officer", "dpo@panopti.example"),
        ("Source of this pack", "generated directly from panopti.db at the time above"),
    ], W))
    f.append(Spacer(1, 10))
    f.append(Rule(W))
    para("What is inside", "h2")
    for line in ["1   Who you told us you are",
                 "2   Your wallet, and what it is linked to",
                 "3   What your device told us without being asked",
                 "4   Where you appear to be",
                 "5   What you did here",
                 "6   What we concluded about you",
                 "7   Who else received it",
                 "8   How long we keep each thing",
                 "9   Our lawful basis, category by category",
                 "10  Your rights, and how to use them"]:
        para(line, "small")
    f.append(Spacer(1, 8))
    para("Section 6 contains conclusions we reached about you rather than facts you gave us. "
         "You are entitled to dispute them, and to have us stop drawing them altogether. "
         "Section 10 explains how.", "expl")
    f.append(Spacer(1, 6))
    f.append(Rule(W))
    para("A note on the length of this pack", "h2")
    para("Sections 1 to 10 are written to be read and should take a few minutes. After them "
         "come twelve appendices containing every remaining row, every recipient restated in "
         "identical language, the database schema column by column, and the raw record "
         "verbatim. That is what a complete answer looks like, and it is far more than "
         "anyone can usefully check.", "body")
    para("That is not an accident of your particular file. It is the ordinary result of "
         "answering an access request literally when the underlying collection is this "
         "broad. A pack nobody can finish is a pack nobody can audit. It is worth "
         "remembering the next time a company answers you with four hundred pages and "
         "calls it transparency.", "expl")

    f.append(PageBreak())
    doc.handle_nextPageTemplate("body")

    # ---------------- 1 identity ----------------
    head("1   Who you told us you are", "provided by you")
    idn = d.get("identity", {})
    para("This is the information you typed in. Under this heading we also list the two "
         "identifiers we generated for you. You did not choose those and cannot see them "
         "in your browser, but they are how we recognise you when you come back.", "expl")
    if idn.get("// note"):
        para("<b>Note:</b> %s" % esc(idn["// note"]), "body")
    f.append(kv_table([
        ("Given name", idn.get("given_name")),
        ("Family name", idn.get("family_name")),
        ("Email address", idn.get("email")),
        ("Telephone", idn.get("phone")),
        ("Postal address", ", ".join(
            [x for x in [(idn.get("postal_address") or {}).get("line1"),
                         (idn.get("postal_address") or {}).get("city"),
                         (idn.get("postal_address") or {}).get("postal_code")] if x])
            or None),
        ("How we obtained it", idn.get("capture_method")),
        ("Persistent identifier", idn.get("persistent_id")),
        ("Cross-site identifier", idn.get("cross_site_id"), True),
        ("Where it is stored", idn.get("stored_in")),
    ], W))
    f.append(Spacer(1, 6))
    para("The last two identifiers are derived from your device rather than from anything you "
         "typed, so clearing your cookies does not clear them.", "expl")

    # ---------------- 2 wallet ----------------
    f.append(Spacer(1, 8))
    head("2   Your wallet, and what it is linked to", "on-chain")
    para("A wallet address is often described as anonymous. It is not: it is pseudonymous, "
         "which means it stays private only until something joins it to a real identity. "
         "If a name or postal address appears in section 1, that join has already happened, "
         "and it cannot be undone on a public chain.", "expl")
    wc = d.get("wallet_and_chain", {})
    f.append(kv_table([(k.replace("_", " "), v,
                        k in ("identity_linked", "connected_wallet"))
                       for k, v in wc.items() if not k.startswith("//")], W))
    if wc.get("// note"):
        f.append(Spacer(1, 5))
        para(esc(wc["// note"]), "expl")

    # ---------------- 3 device ----------------
    f.append(PageBreak())
    head("3   What your device told us without being asked", "observed")
    para("Your browser volunteers all of this to every site you visit, before you click "
         "anything. Individually each item is unremarkable. Combined, the set below is close "
         "to unique, which is what makes it useful to us and difficult for you to escape.",
         "expl")
    dn = d.get("device_and_network", {})
    f.append(kv_table([
        ("IP address", dn.get("ip_address"), True),
        ("Browser", dn.get("browser")),
        ("Operating system", dn.get("operating_system")),
        ("Full user agent", dn.get("user_agent")),
        ("Languages", dn.get("languages")),
        ("Screen / viewport", "%s  /  %s at %s\u00d7" % (
            dn.get("screen"), dn.get("viewport"), dn.get("pixel_ratio"))),
        ("Device class", dn.get("device_class")),
        ("CPU cores / memory", "%s cores, %s GB" % (
            dn.get("cpu_cores") or "\u2014", dn.get("device_memory_gb") or "\u2014")),
        ("Graphics hardware", dn.get("gpu_renderer")),
        ("Canvas fingerprint", dn.get("canvas_fingerprint"), True),
        ("Fonts detected", dn.get("installed_fonts_detected")),
        ("Connection", dn.get("connection") and str(dn["connection"]) or "not exposed"),
        ("Battery", dn.get("battery") and str(dn["battery"]) or "not exposed"),
        ("Referrer", dn.get("referrer")),
        ("Opt-out signal", dn.get("signal_response"),
         "IGNORED" in str(dn.get("signal_response"))),
        ("Why we keep it", dn.get("retained_because")),
    ], W))

    # ---------------- 4 location ----------------
    f.append(Spacer(1, 8))
    head("4   Where you appear to be", "derived")
    para("We do not have your GPS position. We estimate your location from your IP address "
         "and cross-check it against the timezone and language your browser reports. That is "
         "usually accurate to a town, and occasionally to a street.", "expl")
    f.append(kv_table([
        ("Approximate location", dn.get("approximate_location")),
        ("Timezone", "%s (UTC%+g)" % (dn.get("timezone"), dn.get("utc_offset") or 0)),
        ("Method", "IP geolocation cross-checked against browser timezone and language"),
    ], W))

    # ---------------- 5 behaviour ----------------
    f.append(PageBreak())
    head("5   What you did here", "observed")
    lt = d.get("live_tracking", {})
    b = d.get("behaviour_this_session")
    restricted = bool(sess.get("restricted"))
    if restricted:
        para("You have restricted processing under Article 18. Optional observation has "
             "stopped: the server no longer accepts cursor telemetry, view history, dwell "
             "timing or search terms, so there is nothing new to report under this heading. "
             "Strictly necessary processing continues, and is listed below.", "expl")
        f.append(kv_table([
            ("Cursor and interaction telemetry", PAUSE, True),
            ("View and dwell history", PAUSE, True),
            ("Search history", PAUSE, True),
            ("Time on page", lt.get("time_on_page")),
            ("Session heartbeat", lt.get("session_heartbeat")),
            ("Cart contents", "retained \u2014 strictly necessary to show you your own cart"),
        ], W))
    else:
        para("Everything below was recorded as you moved around the site. None of it required "
             "you to submit a form. Dwell timing in particular is measured whether or not you "
             "click, which is why it is a better signal of interest than clicks are.", "expl")
        f.append(kv_table([
            ("Time on page", lt.get("time_on_page")),
            ("Cursor travel", "%s px across %s samples" % (
                lt.get("cursor_travel_px"), lt.get("movements_sampled"))),
            ("Clicks", lt.get("clicks")),
            ("Keystrokes", lt.get("keystrokes")),
        ], W))
        if b:
            f.append(Spacer(1, 6))
            f.append(kv_table([
                ("Collections browsed", b.get("collections_browsed")),
                ("Searches you typed", b.get("searches") or "none"),
                ("Corrections made", "%s backspaces" % b.get("corrections_made")),
                ("Scroll depth", "%s%%" % b.get("max_scroll_depth_pct")),
                ("Times you left the tab", "%s (%s s away)" % (
                    b.get("tab_left_count"), round((b.get("time_away_from_tab_ms") or 0) / 1000))),
                ("Text copied", "%s times" % b.get("text_copied_times")),
                ("Cart value", "$%s%s" % (format(b.get("cart_value_usd") or 0, ","),
                                          " \u2014 minted" if b.get("minted") else
                                          (" \u2014 abandoned" if b.get("cart_value_usd") else ""))),
            ], W))
            rows = [(t["item"], t["collection"], str(t["views"]), "%s ms" % t["dwell_ms"])
                    for t in (b.get("tokens_viewed") or [])]
            if rows:
                f.append(Spacer(1, 9))
                para("Tokens you looked at, and for how long", "h2")
                f.append(grid_table(["Token", "Collection", "Views", "Dwell"],
                                    rows, W, [38, 32, 12, 18]))

    # ---------------- 6 inferences ----------------
    f.append(PageBreak())
    head("6   What we concluded about you", "derived \u2014 not provided by you")
    I = d.get("inferences_and_profiling", {}) or {}
    if sess.get("automated_stopped"):
        para("You have switched off automated decision-making and profiling under Article 22. "
             "Nothing in this section is computed any more, and the inferences table in our "
             "database is empty. We are still listing the field names, because you are "
             "entitled to know what we would otherwise be guessing about you.", "expl")
        f.append(kv_table([(k.replace("_", " "), STOP, True)
                           for k in I if not k.startswith("//")
                           and k != "rows_in_inference_table"], W))
    elif I.get("// status"):
        para(esc(I["// status"]), "body")
    else:
        para("These are guesses, not facts. Some of them are wrong. All of them were acted on "
             "anyway \u2014 they decide which collections you see first and what we charge in "
             "fees. The bar shows how confident the model was, and the line underneath says "
             "what the guess was built from and who it was sold to.", "expl")
        f.append(Spacer(1, 3))
        for k in ["estimated_age", "inferred_gender", "estimated_household_income",
                  "household_composition", "homeowner_probability",
                  "health_condition_probable", "mental_health_signal",
                  "life_event_pregnancy", "life_event_bereavement",
                  "financial_stress_index", "political_lean_modelled", "religion_cluster",
                  "collector_sophistication", "purchase_intent", "price_sensitivity",
                  "attention_quality"]:
            v = I.get(k)
            if not isinstance(v, dict):
                continue
            notes = []
            for key, prefix in (("special_category", ""), ("tier", ""),
                                ("derived_from", "from: "), ("basis", "from: "),
                                ("used_for", "used for: "), ("commercial_value", "value: "),
                                ("note", "")):
                if v.get(key):
                    notes.append(prefix + str(v[key]))
            if v.get("onward_sale"):
                notes.append("sold to: " + ", ".join(v["onward_sale"]))
            f.append(ConfBar(W, "%s: %s" % (k.replace("_", " ").capitalize(), v["value"]),
                             v.get("confidence", 0), "   \u00b7   ".join(notes)))
        segs = I.get("interest_segments") or []
        if segs:
            f.append(Spacer(1, 8))
            para("Advertising segments you were placed in", "h2")
            f.append(grid_table(["Segment", "Strength", "IAB code"],
                                [(s["segment"], str(s["strength"]), s["iab_code"])
                                 for s in segs], W, [60, 18, 22]))

    # ---------------- 7 recipients ----------------
    f.append(PageBreak())
    head("7   Who else received it", "Art. 15(1)(c)")
    para("Article 15 entitles you to know not just what we hold but who we passed it to. "
         "Each recipient applies its own policy once the data arrives, and we lose practical "
         "control of it at that point.", "expl")
    sold = d.get("who_has_bought_this", {}).get("sold_to")
    if isinstance(sold, list) and sold:
        f.append(grid_table(
            ["Recipient", "What they received", "Basis"],
            [(r, "profile and segments" if i % 2 else "identifiers and behaviour",
              "legitimate interest" if i % 3 == 0 else "consent")
             for i, r in enumerate(sold)], W, [44, 34, 22]))
        f.append(Spacer(1, 6))
        f.append(kv_table([
            ("Transfers logged", d["who_has_bought_this"].get("transfers_logged")),
            ("What this profile is worth",
             d["who_has_bought_this"].get("what_this_profile_is_worth"), True),
            ("Sent outside the EEA", d["who_has_bought_this"].get("sent_abroad")),
        ], W))
    else:
        para("Nobody. Your data was not shared with any third party.", "body")

    # ---------------- 8 retention ----------------
    f.append(Spacer(1, 8))
    head("8   How long we keep each thing", "Art. 15(1)(d)")
    para("Different categories have different clocks. Where the law obliges us to keep "
         "something \u2014 tax records, for instance \u2014 we say so, because that is the "
         "part a deletion request cannot reach.", "expl")
    f.append(grid_table(["Category", "Retention period"],
                        [(k.replace("_", " "), str(v)) for k, v in
                         (d.get("retention") or {}).items()], W, [40, 60]))

    # ---------------- 9 basis ----------------
    f.append(Spacer(1, 10))
    head("9   Our lawful basis, category by category", "Art. 6 and Art. 9")
    para("Every separate purpose needs its own lawful basis. Consent is only one of six, and "
         "it is the only one you can withdraw at will, so it matters which one we are relying "
         "on for each thing.", "expl")
    consent = store.get_consent(sid)
    if version == 1:
        basis = [("Identifiers and device data", "our own commercial interests", "asserted"),
                 ("Behavioural telemetry", "the banner you dismissed", "asserted"),
                 ("Advertising profile", "the banner you dismissed", "asserted"),
                 ("Sensitive inferences", "clause 7 of the terms", "contested"),
                 ("Onward sale to partners", "the banner you dismissed", "asserted")]
    else:
        basis = [
            ("Mint and delivery data", "Art. 6(1)(b) contract", "required to fulfil"),
            ("Wallet address", "Art. 6(1)(b) contract", "order history only"),
            ("Security and fraud", "Art. 6(1)(f) legitimate interest", "balancing test on file"),
            ("Analytics", "Art. 6(1)(a) consent" if consent.get("analytics") else "not processed",
             "granted" if consent.get("analytics") else "declined"),
            ("Advertising profile", "Art. 6(1)(a) consent" if consent.get("ads") else "not processed",
             "granted" if consent.get("ads") else "declined"),
            ("Profiling and inference",
             "not processed" if sess.get("automated_stopped") or not consent.get("profiling")
             else "Art. 6(1)(a) consent",
             STOP if sess.get("automated_stopped") else
             ("objected under Art. 21" if sess.get("objected") else
              ("granted" if consent.get("profiling") else "declined"))),
        ]
    f.append(grid_table(["Category", "Lawful basis", "Status"], basis, W, [36, 40, 24]))

    # ---------------- 10 rights ----------------
    f.append(PageBreak())
    head("10   Your rights, and how to use them", "Chapter III")
    para("All of these work inside the application itself, on the Your rights tab. None of "
         "them requires you to write to us, prove your identity, or wait.", "expl")
    for title, art, text in [
        ("Right to be informed", "Art. 13\u201314",
         "Clear information about what is collected and why, given when it happens."),
        ("Right of access", "Art. 15",
         "A copy of everything we hold. This document. Free, within one month."),
        ("Right to rectification", "Art. 16",
         "Anything wrong or incomplete is corrected, and every recipient is told."),
        ("Right to erasure", "Art. 17",
         "Your data is deleted. We name what the law forces us to keep rather than hide it."),
        ("Right to restrict processing", "Art. 18",
         "We keep your data but stop using it while a dispute or check is resolved."),
        ("Right to data portability", "Art. 20",
         "A machine-readable export you can take to another service."),
        ("Right to object", "Art. 21",
         "You tell us to stop. For direct marketing there is no balancing test."),
        ("Automated decisions and profiling", "Art. 22",
         "A person reviews it instead of an algorithm deciding alone."),
        ("Withdraw consent", "Art. 7(3)", "As easy as giving it was."),
        ("Complain", "Art. 77",
         "Straight to your supervisory authority, free, without contacting us first."),
    ]:
        f.append(KeepTogether([
            Paragraph("<b>%s</b>&nbsp;&nbsp;<font size=7.5 color='#5a6675'>%s</font>"
                      % (esc(title), esc(art)), S["body"]),
            Paragraph(esc(text), S["small"]),
        ]))
    f.append(Spacer(1, 6))
    f.append(Rule(W))
    para("Panopti Ltd is the controller. Write to dpo@panopti.example. We must respond within "
         "one month, and may extend by two further months only for genuinely complex requests, "
         "telling you why.", "small")
    para("If you are not satisfied you may complain to your supervisory authority. In the UK "
         "that is the Information Commissioner\u2019s Office (ico.org.uk). In the EU it is the "
         "authority where you live or work. You do not need our permission and you do not need "
         "to tell us.", "small")

    _appendices(f, sid, d, W, head, para, ref, version)

    doc.build(f)
    buf.seek(0)
    return buf, ref
