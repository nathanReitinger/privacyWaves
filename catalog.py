"""Panopti catalogue: nine collections, and a deterministic pixel-art generator.

Every token's artwork is derived from the SHA-256 of its id, so the same token
always renders identically and no two tokens can collide. The first ten hex
characters of that digest are shown on the card as proof.
"""
import hashlib

# --------------------------------------------------------------------------
# collections
# --------------------------------------------------------------------------
COLLECTIONS = [
    {"id": "pixel", "name": "Pixel Pals", "blurb": "Small friends, large pixels.", "items": [
        {"id": "owl",   "n": "Sleepless Pixel Owl",        "p": 255,  "b": "Awake since block 14,201,003.",        "sig": ["sleep", "anxiety", "whimsy"]},
        {"id": "frog",  "n": "Pixel Frog in a Hat",        "p": 128,  "b": "The hat is not removable. Ever.",       "sig": ["whimsy", "home"]},
        {"id": "hand",  "n": "Toddler Handprint #4",       "p": 380,  "b": "Minted by someone very small.",         "sig": ["kids", "lifeevent"]},
        {"id": "loaf",  "n": "Cat Loaf, Fully Risen",      "p": 190,  "b": "Structurally a bread. Legally a cat.",  "sig": ["whimsy", "kids"]},
        {"id": "sigh",  "n": "Dog That Sighs",             "p": 160,  "b": "Loops forever. Audibly disappointed.",  "sig": ["whimsy"]},
    ]},
    {"id": "apes", "name": "Sad Beige Apes", "blurb": "Ten thousand of them. Nine remain.", "items": [
        {"id": "ape1",  "n": "Beige Ape #0001",            "p": 13400, "b": "The original. Very tired.",            "sig": ["status", "luxury"]},
        {"id": "ape2",  "n": "Beige Ape, Yawning",         "p": 6700,  "b": "Rare trait: visible molars.",          "sig": ["status", "luxury"]},
        {"id": "ape3",  "n": "Beige Ape With Lanyard",     "p": 5890,  "b": "Attended the conference. Regrets it.", "sig": ["status", "work"]},
        {"id": "ape4",  "n": "Beige Ape, Underwater",      "p": 3020,  "b": "Not drowning. Simply beneath.",        "sig": ["status"]},
        {"id": "ape5",  "n": "Beige Ape Refinancing",      "p": 985,   "b": "Down 94% and still posting.",          "sig": ["status", "financial", "budget"]},
    ]},
    {"id": "rocks", "name": "Emotional Support Rocks", "blurb": "Igneous. Patient. Non-judgemental.", "items": [
        {"id": "rock1", "n": "Support Rock #12",           "p": 95,   "b": "Holds still while you talk.",           "sig": ["anxiety", "health"]},
        {"id": "rock2", "n": "Rock That Listens",          "p": 130,  "b": "No advice. None at all.",               "sig": ["anxiety"]},
        {"id": "rock3", "n": "Rock Under a Weighted Blanket", "p": 290, "b": "Seven kilos on four hundred grams.",  "sig": ["anxiety", "sleep", "health"]},
        {"id": "rock4", "n": "Rock Prescribed by Nobody",  "p": 225,  "b": "Take one. Do not consult anyone.",      "sig": ["health", "anxiety"]},
        {"id": "rock5", "n": "Rock at 3AM",                "p": 350,  "b": "Same rock. Worse hour.",                "sig": ["sleep", "anxiety"]},
    ]},
    {"id": "office", "name": "Haunted Office Supplies", "blurb": "They stayed after the layoffs.", "items": [
        {"id": "stap",  "n": "Stapler That Knows",         "p": 165,  "b": "It has read your calendar.",            "sig": ["work", "whimsy"]},
        {"id": "lam",   "n": "Possessed Laminator",        "p": 195,  "b": "Preserves things that asked not to be.","sig": ["work"]},
        {"id": "lan",   "n": "The Lanyard",                "p": 64,   "b": "Still warm.",                           "sig": ["work", "status"]},
        {"id": "chair", "n": "Chair With Opinions",        "p": 140,  "b": "Reclines only in disagreement.",        "sig": ["work"]},
        {"id": "print", "n": "Printer, Screaming",         "p": 255,  "b": "PC LOAD LETTER, forever.",              "sig": ["work", "whimsy", "anxiety"]},
    ]},
    {"id": "build", "name": "Very Small Buildings", "blurb": "To scale, but the scale is tiny.", "items": [
        {"id": "shed",  "n": "Shed, Perfect",              "p": 445,  "b": "Nothing inside. Ideal.",                "sig": ["home", "hobby"]},
        {"id": "bung",  "n": "Bungalow The Size Of A Stamp","p": 700, "b": "Freehold. Unlivable.",                  "sig": ["home"]},
        {"id": "boll",  "n": "A Single Bollard",           "p": 32,   "b": "Protects nothing in particular.",       "sig": ["outdoor", "whimsy"]},
        {"id": "phone", "n": "Phone Box, Unused",          "p": 285,  "b": "Last call: 1998.",                      "sig": ["retired", "home"]},
        {"id": "gar",   "n": "Garage With A Boat In It",   "p": 1050, "b": "The boat has never been wet.",          "sig": ["hobby", "outdoor", "retired"]},
    ]},
    {"id": "clouds", "name": "Certified Clouds", "blurb": "Notarised by a meteorologist we found.", "items": [
        {"id": "cl4",    "n": "Cloud #4 (Cumulus)",        "p": 160,  "b": "Fluffy. Unremarkable. Yours.",          "sig": ["outdoor"]},
        {"id": "regret", "n": "Cloud That Looks Like Regret","p": 225,"b": "Everyone sees something different.",    "sig": ["anxiety"]},
        {"id": "damp",   "n": "Cloud, Slightly Damp",      "p": 95,   "b": "Not raining. Considering it.",          "sig": ["outdoor"]},
        {"id": "sun",    "n": "Sunset, Over-Saturated",    "p": 380,  "b": "No filter. There is a filter.",         "sig": ["outdoor", "whimsy"]},
        {"id": "fog",    "n": "Fog, Local",                "p": 128,  "b": "Sourced within ten miles.",             "sig": ["outdoor"]},
    ]},
    {"id": "snacks", "name": "Discontinued Snacks", "blurb": "Gone from shelves. Forever on-chain.", "items": [
        {"id": "ramen", "n": "Instant Noodle Brick",       "p": 64,   "b": "Forty-eight in a box. Again.",          "sig": ["budget", "financial", "bulk"]},
        {"id": "crisp", "n": "Value Crisps, 48 Bags",      "p": 95,   "b": 'The flavour was "flavour".',            "sig": ["budget", "bulk", "financial"]},
        {"id": "choc",  "n": "The Last Good Chocolate Bar","p": 190,  "b": "Reformulated in 2014. Mourned since.",  "sig": ["food", "whimsy"]},
        {"id": "cola",  "n": "Own-Brand Cola",             "p": 64,   "b": "Technically a cola.",                   "sig": ["budget", "food"]},
        {"id": "egg",   "n": "Pickled Egg, Jarred",        "p": 128,  "b": "Divisive. Immutable.",                  "sig": ["food", "whimsy"]},
    ]},
    {"id": "liminal", "name": "Liminal Carpets", "blurb": "Rooms you have been in but cannot name.", "items": [
        {"id": "hotel",  "n": "Hotel Corridor, 2:14AM",    "p": 475,  "b": "The ice machine is down the hall.",     "sig": ["sleep", "anxiety"]},
        {"id": "wait",   "n": "Waiting Room Carpet",       "p": 255,  "b": "Nineteen chairs. One magazine.",        "sig": ["health", "anxiety"]},
        {"id": "scan",   "n": "First Scan, Blurred",       "p": 920,  "b": "Twelve weeks. Grainy. Priceless.",      "sig": ["pregnancy", "lifeevent", "health"]},
        {"id": "candle", "n": "In Loving Memory, Candle",  "p": 160,  "b": "Burns at a constant rate.",             "sig": ["grief", "lifeevent"]},
        {"id": "gate",   "n": "Airport Gate, Empty",       "p": 320,  "b": "Boarding closed. Nobody came.",         "sig": ["anxiety"]},
    ]},
    {"id": "sounds", "name": "Sounds You Forgot", "blurb": "Audio tokens. Yes, that is a thing here.", "items": [
        {"id": "det",   "n": "Metal Detector Beep",        "p": 190,  "b": "Recorded on a beach in 2004.",          "sig": ["hobby", "retired", "outdoor"]},
        {"id": "dial",  "n": "Dial-Up Handshake",          "p": 285,  "b": "Fourteen seconds of pure dread.",       "sig": ["retired", "whimsy"]},
        {"id": "nok",   "n": "Nokia Ringtone, Muffled",    "p": 160,  "b": "From inside a coat pocket.",            "sig": ["retired"]},
        {"id": "coin",  "n": "Coin in a Payphone",         "p": 95,   "b": "Clunk. Whirr. Clunk.",                  "sig": ["retired", "budget"]},
    ]},
]

# Roughly half the catalogue uses a plain emoji instead of generated pixel art,
# so the grid reads as a mix of the ordinary and the procedural rather than a
# wall of noise. Both kinds still carry their own digest on the card.
EMOJI = {
    "owl": "\U0001F989", "hand": "\U0001F590\uFE0F", "loaf": "\U0001F431",
    "ape1": "\U0001F9A7", "ape5": "\U0001F4C9",
    "rock1": "\U0001FAA8", "rock5": "\U0001F319",
    "stap": "\U0001F4CE", "chair": "\U0001FA91",
    "shed": "\U0001F3DA\uFE0F", "boll": "\U0001F6A7", "phone": "\u260E\uFE0F",
    "cl4": "\u2601\uFE0F", "damp": "\U0001F327\uFE0F", "sun": "\U0001F305",
    "ramen": "\U0001F35C", "cola": "\U0001F964", "egg": "\U0001F95A",
    "hotel": "\U0001F3E8", "candle": "\U0001F56F\uFE0F", "gate": "\u2708\uFE0F",
    "det": "\U0001F50D", "nok": "\U0001F4F1", "coin": "\U0001FA99",
}

PRODUCTS = {}
for _c in COLLECTIONS:
    for _i in _c["items"]:
        PRODUCTS[_i["id"]] = dict(_i, coll=_c["id"], coll_name=_c["name"],
                                  e=EMOJI.get(_i["id"]))


# --------------------------------------------------------------------------
# deterministic pixel art
# --------------------------------------------------------------------------
def token_hash(tid: str) -> str:
    """Full SHA-256 of the token id. Stable across runs and machines."""
    return hashlib.sha256(("panopti:" + tid).encode()).hexdigest()


def token_hash_short(tid: str) -> str:
    return token_hash(tid)[:10]


class _Rand:
    """Tiny deterministic PRNG seeded from the token digest."""
    def __init__(self, seed_hex: str):
        self.s = int(seed_hex[:16], 16) or 1

    def next(self) -> int:
        # xorshift64
        s = self.s
        s ^= (s << 13) & 0xFFFFFFFFFFFFFFFF
        s ^= s >> 7
        s ^= (s << 17) & 0xFFFFFFFFFFFFFFFF
        self.s = s & 0xFFFFFFFFFFFFFFFF
        return self.s

    def i(self, n: int) -> int:
        return self.next() % n

    def f(self) -> float:
        return (self.next() % 10_000) / 10_000.0


def _hsl(h, s, l):
    """HSL to hex. Hex keeps every renderer happy, including PDF and SVG tools."""
    h = (h % 360) / 360.0
    s = s / 100.0
    l = l / 100.0
    if s == 0:
        r = g = b = l
    else:
        q = l * (1 + s) if l < 0.5 else l + s - l * s
        p_ = 2 * l - q

        def hue(t):
            t = t % 1.0
            if t < 1 / 6: return p_ + (q - p_) * 6 * t
            if t < 1 / 2: return q
            if t < 2 / 3: return p_ + (q - p_) * (2 / 3 - t) * 6
            return p_
        r, g, b = hue(h + 1 / 3), hue(h), hue(h - 1 / 3)
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


def _palette(r: _Rand):
    base = r.i(360)
    scheme = r.i(3)
    if scheme == 0:                      # complementary
        hues = [base, (base + 180) % 360, (base + 30) % 360]
    elif scheme == 1:                    # triad
        hues = [base, (base + 120) % 360, (base + 240) % 360]
    else:                                # analogous
        hues = [base, (base + 35) % 360, (base + 70) % 360]
    ink = [_hsl(hues[0], 78, 52), _hsl(hues[1], 70, 44), _hsl(hues[2], 85, 64)]
    bg = _hsl(base, 30, 93)
    return bg, ink


GRID = 16


def _cells_creature(r):
    """Vertically mirrored sprite — reads as a face or a small animal."""
    cells = {}
    half = GRID // 2
    density = 0.42 + r.f() * 0.2
    for y in range(2, GRID - 2):
        for x in range(1, half):
            if r.f() < density:
                c = r.i(2)
                cells[(x, y)] = c
                cells[(GRID - 1 - x, y)] = c
    # eyes
    ey = 4 + r.i(3)
    for ex in (half - 3 - r.i(2), ):
        cells[(ex, ey)] = 2
        cells[(GRID - 1 - ex, ey)] = 2
    return cells


def _cells_glitch(r):
    """Horizontal scanline displacement — a corrupted JPEG."""
    cells = {}
    y = 0
    while y < GRID:
        h = 1 + r.i(3)
        x = r.i(4)
        while x < GRID:
            w = 1 + r.i(5)
            c = r.i(3)
            if r.f() < 0.72:
                for yy in range(y, min(GRID, y + h)):
                    for xx in range(x, min(GRID, x + w)):
                        cells[(xx, yy)] = c
            x += w + r.i(3)
        y += h
    return cells


def _cells_maze(r):
    """Diagonal tiles — a truchet tiling, the classic 10 PRINT pattern."""
    cells = {}
    step = 2
    for gy in range(0, GRID, step):
        for gx in range(0, GRID, step):
            c = r.i(2)
            flip = r.i(2)
            for k in range(step):
                xx = gx + (k if flip else step - 1 - k)
                yy = gy + k
                if xx < GRID and yy < GRID:
                    cells[(xx, yy)] = c
                    if xx + 1 < GRID:
                        cells[(xx + 1, yy)] = c
    return cells


def _cells_orbit(r):
    """Concentric rings with gaps — a radar sweep or a planet."""
    cells = {}
    cx = cy = (GRID - 1) / 2
    rings = 3 + r.i(3)
    keep = [r.f() < 0.75 for _ in range(rings + 1)]
    for y in range(GRID):
        for x in range(GRID):
            d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            band = int(d / (GRID / 2 / rings))
            if band <= rings and keep[min(band, rings)]:
                if r.f() < 0.88:
                    cells[(x, y)] = band % 3
    return cells


def _cells_stack(r):
    """Chunky blocks piled on a ground line — a weird object on a shelf."""
    cells = {}
    for x in range(GRID):                     # ground
        cells[(x, GRID - 1)] = 2
        cells[(x, GRID - 2)] = 2
    y = GRID - 2
    for _ in range(3 + r.i(3)):
        h = 2 + r.i(3)
        w = 4 + r.i(8)
        x = r.i(max(1, GRID - w))
        c = r.i(3)
        for yy in range(max(0, y - h), y):
            for xx in range(x, min(GRID, x + w)):
                cells[(xx, yy)] = c
        # a notch, so the silhouette is not a plain rectangle
        if r.f() < 0.6 and w > 4:
            nx = x + 1 + r.i(w - 3)
            cells.pop((nx, max(0, y - h)), None)
            cells.pop((nx + 1, max(0, y - h)), None)
        y -= h
        if y <= 2:
            break
    return cells


_STYLES = [_cells_creature, _cells_glitch, _cells_maze, _cells_orbit, _cells_stack]
_STYLE_NAMES = ["creature", "glitch", "truchet", "orbit", "stack"]


def art_style(tid: str) -> str:
    r = _Rand(token_hash(tid))
    r.i(97)  # burn, matches art_svg ordering
    return _STYLE_NAMES[r.i(len(_STYLES))]


def art_svg(tid: str, px: int = 12) -> str:
    """Render the token's artwork as a standalone SVG string."""
    digest = token_hash(tid)
    r = _Rand(digest)
    r.i(97)
    style_ix = r.i(len(_STYLES))
    bg, ink = _palette(r)
    cells = _STYLES[style_ix](r)

    size = GRID * px
    out = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" '
        'width="%d" height="%d" shape-rendering="crispEdges" role="img" '
        'aria-label="Generated artwork for token %s">' % (size, size, size, size, tid),
        '<rect width="%d" height="%d" fill="%s"/>' % (size, size, bg),
    ]
    for (x, y), c in cells.items():
        out.append('<rect x="%d" y="%d" width="%d" height="%d" fill="%s"/>'
                   % (x * px, y * px, px, px, ink[c % 3]))
    # a faint grid, so it reads as pixels rather than as a photo
    out.append('<g stroke="rgba(0,0,0,.06)" stroke-width="1">')
    for i in range(1, GRID):
        out.append('<line x1="%d" y1="0" x2="%d" y2="%d"/>' % (i * px, i * px, size))
        out.append('<line x1="0" y1="%d" x2="%d" y2="%d"/>' % (i * px, size, i * px))
    out.append('</g></svg>')
    return "".join(out)


def catalog_payload():
    """Everything the browser needs to draw the marketplace."""
    colls = []
    for c in COLLECTIONS:
        items = []
        for i in c["items"]:
            items.append({
                "id": i["id"], "n": i["n"], "p": i["p"], "b": i["b"],
                "hash": token_hash_short(i["id"]),
                "e": EMOJI.get(i["id"]),
                "style": "emoji" if i["id"] in EMOJI else art_style(i["id"]),
            })
        colls.append({"id": c["id"], "name": c["name"], "blurb": c["blurb"],
                      "floor": min(i["p"] for i in c["items"]), "items": items})
    return colls


# --------------------------------------------------------------------------
# fabricated provenance
#
# Every token needs an artist, and the artist has to be stable: the same token
# must always credit the same person, or the "proof" on the card means nothing.
# So the name, the city, the year and the edition all come out of the same
# digest that drew the picture.
# --------------------------------------------------------------------------
_FIRST = ["Marisol", "Tobias", "Ines", "Kwame", "Saoirse", "Dmitri", "Noor", "Emeka",
          "Yuki", "Rafael", "Ingrid", "Halim", "Beatrix", "Jonas", "Liora", "Anselm",
          "Petra", "Osian", "Mireille", "Caspar", "Rhoda", "Teodor", "Amara", "Silje"]
_LAST = ["Vantongeren", "Okonkwo", "Brannigan", "Delacroix-Mbeki", "Hallstrom",
         "Oyelaran", "Kirchmayr", "Santorini", "Prishtina", "Waldegrave", "Novak-Reyes",
         "Fairweather", "Dziedzic", "Bellingham", "Ferreira", "Lindqvist", "Achebe",
         "Moravec", "Thistlewood", "Nakagawa", "Oduya", "Rasmussen", "Calloway", "Ferrante"]
_CITY = ["Lisbon", "Tbilisi", "Rotterdam", "Lagos", "Montreal", "Naples", "Bergen",
         "Kyoto", "Valparaiso", "Tallinn", "Dakar", "Glasgow", "Medellin", "Ghent",
         "Reykjavik", "Hanoi", "Porto", "Wroclaw", "Helsinki", "Mombasa"]
_MEDIUM = ["generative SVG", "hand-placed pixels", "algorithmic weave", "plotter study",
           "16×16 gouache scan", "recovered dither", "single-pass raster", "chance operation"]
_BIO = [
    "works exclusively at 16 by 16 pixels and refuses to explain why",
    "came to generative work from ceramics and still thinks in glazes",
    "spent nine years as a cartographer before switching to tokens",
    "makes one piece a week and destroys the ones that come easily",
    "only works between 3am and dawn, which they insist is a formal constraint",
    "trained as a structural engineer and treats every canvas as a load problem",
    "has never shown work in a physical gallery and does not intend to",
    "collaborates with a plotter they have named and will not replace",
    "believes the grid is a moral position rather than an aesthetic one",
    "sold their first piece for eleven dollars and their last for considerably more",
]
_TRAIT_NAMES = ["Palette", "Density", "Symmetry", "Grain", "Mood", "Aperture"]
_TRAIT_VALS = {
    "Palette": ["Complementary", "Triadic", "Analogous", "Split", "Muted", "Acid"],
    "Density": ["Sparse", "Open", "Balanced", "Packed", "Saturated"],
    "Symmetry": ["Mirrored", "Rotational", "Broken", "None", "Near"],
    "Grain": ["Crisp", "Soft", "Dithered", "Banded", "Torn"],
    "Mood": ["Placid", "Uneasy", "Cheerful", "Liminal", "Wry", "Bereft"],
    "Aperture": ["Closed", "Half", "Wide", "Blown"],
}


def token_detail(tid):
    """Everything the large view shows. Deterministic, so it never shifts."""
    if tid not in PRODUCTS:
        return None
    p = PRODUCTS[tid]
    digest = token_hash(tid)
    r = _Rand(digest)

    first, last = _FIRST[r.i(len(_FIRST))], _LAST[r.i(len(_LAST))]
    city = _CITY[r.i(len(_CITY))]
    year = 2017 + r.i(9)
    edition_of = [1, 1, 3, 5, 8, 12, 25, 50][r.i(8)]
    edition_no = 1 + r.i(edition_of)

    traits = []
    for name in _TRAIT_NAMES:
        opts = _TRAIT_VALS[name]
        val = opts[r.i(len(opts))]
        # a rarity figure, so the page has the one number every marketplace shows
        traits.append({"name": name, "value": val, "rarity": "%.1f%%" % (2 + r.i(380) / 10.0)})

    return {
        "id": tid, "name": p["n"], "blurb": p["b"], "price": p["p"],
        "collection": p["coll_name"], "emoji": p.get("e"),
        "hash": digest, "hash_short": digest[:10],
        "style": "emoji" if p.get("e") else art_style(tid),
        "artist": {
            "name": "%s %s" % (first, last),
            "handle": "@%s%s" % (first[:3].lower(), last[:4].lower()),
            "city": city,
            "bio": "%s %s %s." % (first, last, _BIO[r.i(len(_BIO))]),
            "medium": _MEDIUM[r.i(len(_MEDIUM))],
            "year": year,
            "works": 12 + r.i(400),
        },
        "edition": "%d of %d" % (edition_no, edition_of),
        "traits": traits,
        "minted": "block %s" % format(14000000 + int(digest[:6], 16) % 900000, ","),
    }
