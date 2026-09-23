"""The advertising layer.

Twenty-one campaigns. Which ones you see is decided from the inferences in
profiler.py, and every impression and conversion is priced, so the panel can
show what you are worth in dollars.

Two rules hold throughout:

1. The ad is ALWAYS bespoke. With no behavioural signal yet, the rationale
   falls back to your device, your timezone and the hour, which is still enough
   to place you in a priced tier. There is no untargeted ad here, only a
   cheaper one.

2. Opting out replaces everything with the house ad, which earns nothing. That
   contrast is the whole argument.

Rates are roughly what these segments fetch in reality. General retail display
is worth a fraction of a cent per impression; health, debt and life-event
inventory is worth many multiples of it.
"""
import random

HOUSE = {
    "id": "house", "advertiser": "Panopti", "category": "house",
    "headline": "Mint something strange today",
    "body": "Forty-four tokens. No profile was used to choose this.",
    "cta": "Browse", "art": "\U0001F441", "tone": "house",
    "cpm": 0.0, "cpc": 0.0,
    "segment": "none \u2014 untargeted inventory",
    "why": "No profile was used. This is the house ad, and it earns us nothing, "
           "which is exactly what an opted-out visitor is worth to an advertiser.",
}

ADS = [
    {"id": "shoes", "advertiser": "Hoka Meridian", "category": "footwear",
     "headline": "The shoe for people who stand all day", "art": "\U0001F45F",
     "body": "Free returns. Ships tomorrow. 40% off your first pair.",
     "cta": "Shop shoes", "tone": "retail", "cpm": 2.40, "cpc": 0.62,
     "sig": {"outdoor": 2, "hobby": 2},
     "segment": "Active lifestyle, retail intender",
     "why": "Outdoor and hobby browsing puts you in an active-lifestyle retail bucket."},

    {"id": "watch", "advertiser": "Horolo Pre-Owned", "category": "luxury",
     "headline": "Somebody else already took the depreciation", "art": "\u231A",
     "body": "Certified pre-owned. Authenticated in Geneva. Finance available.",
     "cta": "View watches", "tone": "retail", "cpm": 6.80, "cpc": 2.40,
     "sig": {"luxury": 2, "status": 2},
     "segment": "Aspirational luxury, high basket value",
     "why": "High-floor collections put you in an aspirational luxury tier, which "
            "resells at a premium."},

    {"id": "teeth", "advertiser": "Brightbite", "category": "cosmetic",
     "headline": "Straighter teeth in six months", "art": "\U0001F9B7",
     "body": "Clear aligners by post. No appointments. From $89 a month.",
     "cta": "Take the smile quiz", "tone": "retail", "cpm": 7.20, "cpc": 2.90,
     "sig": {"status": 2, "work": 1},
     "segment": "Appearance-conscious, credit-eligible",
     "why": "Status-signalling browsing plus a workday visit puts you in an "
            "appearance-conscious segment with monthly-payment appetite."},

    {"id": "pet", "advertiser": "Snoutwise", "category": "pets",
     "headline": "Your dog deserves better than this", "art": "\U0001F415",
     "body": "Fresh food, portioned for your dog. First box half price.",
     "cta": "Build a plan", "tone": "retail", "cpm": 3.10, "cpc": 1.05,
     "sig": {"whimsy": 3, "kids": 1},
     "segment": "Pet household (probable)",
     "why": "Whimsical browsing correlates with pet ownership. We have not seen a "
            "dog. We are confident anyway."},

    {"id": "lisbon", "advertiser": "Aeglos Travel", "category": "travel",
     "headline": "Three nights in Lisbon, $312", "art": "\u2708\uFE0F",
     "body": "Flights and a room in Alfama. Tuesday departures. Book by Friday.",
     "cta": "See dates", "tone": "travel", "cpm": 4.60, "cpc": 1.70,
     "sig": {"outdoor": 2, "whimsy": 2},
     "segment": "Short-haul leisure intender",
     "why": "Your browsing and local hour match a short-haul leisure profile. "
            "The Friday deadline is not real."},

    {"id": "cruise", "advertiser": "Northstar Voyages", "category": "travel",
     "headline": "Fourteen nights, one unpacking", "art": "\U0001F6A2",
     "body": "Norwegian fjords. Full board. Solo cabins, no supplement.",
     "cta": "Request a brochure", "tone": "travel", "cpm": 8.40, "cpc": 3.20,
     "sig": {"retired": 2, "hobby": 1},
     "segment": "Older, high disposable income",
     "why": "Nostalgia and hobby collections skew older, and cruise inventory pays "
            "well for that inference whether or not it is right."},

    {"id": "gym", "advertiser": "Ironhaus", "category": "fitness",
     "headline": "January is four months away", "art": "\U0001F3CB\uFE0F",
     "body": "No contract. Open 24 hours. First month free with this ad.",
     "cta": "Claim the month", "tone": "retail", "cpm": 3.80, "cpc": 1.35,
     "sig": {"health": 2, "outdoor": 1},
     "segment": "Fitness intender",
     "why": "Health-adjacent browsing places you in a fitness-intender segment."},

    {"id": "dumpling", "advertiser": "Dumpling Club", "category": "food",
     "headline": "Dinner, solved, for six weeks", "art": "\U0001F95F",
     "body": "Frozen dumplings by post. Twelve flavours. Skip any week.",
     "cta": "Pick flavours", "tone": "food", "cpm": 2.90, "cpc": 0.98,
     "sig": {"food": 2, "budget": 1},
     "segment": "Convenience food subscriber",
     "why": "Food browsing on a weekday is a reliable meal-kit signal."},

    {"id": "pizza", "advertiser": "Crustworthy", "category": "food",
     "headline": "Open until 4am", "art": "\U0001F355",
     "body": "Delivery in 25 minutes. No minimum. Yes, still open.",
     "cta": "Order now", "tone": "food", "cpm": 3.40, "cpc": 1.20,
     "sig": {"sleep": 2, "budget": 1},
     "segment": "Late-night impulse",
     "why": "You are browsing at an hour that correlates with impulse ordering, "
            "and with the sleep segment we already put you in."},

    {"id": "coffee", "advertiser": "Battery Coffee Co.", "category": "food",
     "headline": "Tired is a solvable problem", "art": "\u2615",
     "body": "Double-caffeine blend, ground to order. Subscribe and save 25%.",
     "cta": "Try a bag", "tone": "food", "cpm": 4.10, "cpc": 1.40,
     "sig": {"sleep": 2, "work": 2},
     "segment": "Sleep-deprived, employed",
     "why": "Sleep-adjacent browsing during working hours. We are selling you the "
            "symptom while someone else sells you the cause."},

    {"id": "storage", "advertiser": "Boxwell Storage", "category": "services",
     "headline": "You do not have to throw it away", "art": "\U0001F4E6",
     "body": "Units from $29 a month. Four weeks free. Drive-up access.",
     "cta": "Find a unit", "tone": "retail", "cpm": 5.20, "cpc": 2.10,
     "sig": {"home": 2, "craft": 1, "hoard": 1},
     "segment": "Accumulator, space-constrained",
     "why": "Collecting behaviour and home browsing suggest more possessions than "
            "space, which storage advertisers pay well to reach."},

    {"id": "clean", "advertiser": "Tidewell", "category": "services",
     "headline": "Someone else can do it", "art": "\U0001F9F9",
     "body": "Vetted cleaners, hourly, no subscription. Book in ninety seconds.",
     "cta": "See availability", "tone": "retail", "cpm": 4.40, "cpc": 1.60,
     "sig": {"work": 2, "home": 2},
     "segment": "Time-poor household",
     "why": "Long dwell during working hours reads as time-poor and cash-adequate, "
            "which is the profile domestic services want."},

    {"id": "language", "advertiser": "Linguo", "category": "education",
     "headline": "Ten minutes a day. Allegedly.", "art": "\U0001F99C",
     "body": "Forty languages. Streaks, badges, a bird that guilts you.",
     "cta": "Start free", "tone": "media", "cpm": 2.20, "cpc": 0.74,
     "sig": {"retired": 1, "whimsy": 2},
     "segment": "Self-improvement, gamification-responsive",
     "why": "You respond to progress mechanics. So does their product. That match "
            "is worth money to them, and you are reading this next to a points counter."},

    {"id": "news", "advertiser": "The New York Times", "category": "media",
     "headline": "All of The Times. $1 a week.", "art": "\U0001F4F0",
     "body": "News, Games, Cooking, Wirecutter, The Athletic. Cancel anytime.",
     "cta": "Subscribe", "tone": "media", "cpm": 3.20, "cpc": 0.94,
     "sig": {"work": 1, "retired": 1},
     "segment": "Affluent, long-dwell reader",
     "why": "You read rather than skim, and your device tier places you in an "
            "affluent-reader bucket that subscription products bid up."},

    {"id": "nft", "advertiser": "Vaultly Exchange", "category": "crypto",
     "headline": "Beige Ape #0002 just listed", "art": "\U0001F9A7",
     "body": "Floor is moving. Verified collection. Instant settlement.",
     "cta": "View listing", "tone": "crypto", "cpm": 5.10, "cpc": 1.85,
     "sig": {"status": 2, "luxury": 1},
     "segment": "Crypto-active, high intent",
     "why": "High-floor dwell puts you in a crypto-active segment."},

    {"id": "dating", "advertiser": "Tangent", "category": "dating",
     "headline": "Designed to be deleted. Eventually.", "art": "\U0001F49E",
     "body": "Fewer profiles, longer conversations. Free to join.",
     "cta": "Join free", "tone": "lifeevent", "cpm": 9.10, "cpc": 3.40,
     "sig": {"anxiety": 2, "whimsy": 2},
     "segment": "Single household (probable)",
     "why": "Household composition was inferred, not asked. Dating inventory pays a "
            "premium for that guess even when it is wrong."},

    {"id": "sleep", "advertiser": "Somnia Clinic", "category": "health",
     "headline": "Still awake?", "art": "\U0001F319",
     "body": "Online sleep assessment. No referral. Covered by most insurers.",
     "cta": "Take the assessment", "tone": "health", "cpm": 11.40, "cpc": 4.10,
     "inf": ["health_condition_probable"], "sig": {"sleep": 3},
     "segment": "Probable sleep disorder (inferred)",
     "why": "We inferred a probable sleep disorder from the collections you lingered "
            "on. You never told us this. Health segments bill at roughly five times "
            "general display."},

    {"id": "anxiety", "advertiser": "Clearhead Therapy", "category": "health",
     "headline": "Talk to someone this week", "art": "\U0001F9E0",
     "body": "Licensed therapists, video sessions, first week free.",
     "cta": "Get matched", "tone": "health", "cpm": 9.80, "cpc": 3.55,
     "inf": ["mental_health_signal"], "sig": {"anxiety": 3},
     "segment": "Elevated anxiety indicators (inferred)",
     "why": "Your browsing matched an elevated-anxiety model. This is inferred mental "
            "health data, and it chose this ad."},

    {"id": "baby", "advertiser": "Nestwell Baby", "category": "life event",
     "headline": "Congratulations. Here is 30% off.", "art": "\U0001F37C",
     "body": "Prenatal essentials, delivered monthly. Build your registry early.",
     "cta": "Start registry", "tone": "lifeevent", "cpm": 18.60, "cpc": 6.40,
     "inf": ["life_event_pregnancy"], "sig": {"pregnancy": 2},
     "segment": "Probable first trimester (inferred)",
     "why": "We inferred a probable pregnancy from one browsing session. It is the "
            "most valuable segment we hold, and it is often how a household discovers "
            "that a company knew before the family did."},

    {"id": "debt", "advertiser": "Meridian Credit", "category": "financial",
     "headline": "Consolidate what you owe", "art": "\U0001F4B3",
     "body": "One payment. From 6.9% APR. Checking won't affect your score.",
     "cta": "Check eligibility", "tone": "financial", "cpm": 14.20, "cpc": 5.75,
     "inf": ["financial_stress_index"], "sig": {"budget": 3, "financial": 2},
     "segment": "Financial stress indicators (inferred)",
     "why": "Budget-tier browsing placed you in a financial-stress segment. Lenders "
            "pay most for the people least able to shop around."},

    {"id": "memorial", "advertiser": "Everloom Memorials", "category": "life event",
     "headline": "A keepsake that lasts", "art": "\U0001F54A",
     "body": "Handmade memorial jewellery and engraved frames.",
     "cta": "See the range", "tone": "lifeevent", "cpm": 8.90, "cpc": 3.10,
     "inf": ["life_event_bereavement"], "sig": {"grief": 2},
     "segment": "Recent bereavement (inferred)",
     "why": "We inferred a recent bereavement. No suppression rule was applied, "
            "because nobody wrote one."},

    {"id": "insurance", "advertiser": "Bellwether Life", "category": "financial",
     "headline": "Cover for the people you leave behind", "art": "\U0001F4DC",
     "body": "Term life from $11 a month. No medical for most applicants.",
     "cta": "Get a quote", "tone": "financial", "cpm": 12.60, "cpc": 4.80,
     "inf": ["life_event_bereavement", "life_event_pregnancy"],
     "sig": {"grief": 1, "lifeevent": 2},
     "segment": "Life-event triggered (inferred)",
     "why": "A life event was inferred, and life insurance bids hardest in the weeks "
            "immediately after one."},
]

BY_ID = {a["id"]: a for a in ADS}
BY_ID["house"] = HOUSE

PUBLIC = ("id", "advertiser", "category", "headline", "body", "cta", "art",
          "tone", "why", "segment", "cpm", "cpc")


def public(ad):
    return {k: ad.get(k) for k in PUBLIC}


def _score(ad, counts, inferences):
    score = 0.0
    for key in ad.get("inf", []):
        if key in (inferences or {}):
            conf = (inferences[key] or {}).get("confidence") or 0.5
            score += 10 * float(conf)
    for tag, need in (ad.get("sig") or {}).items():
        have = (counts or {}).get(tag, 0)
        if have >= need:
            score += 1.5 + (have - need) * 0.25
        elif have:
            score += have * 0.4
    return score


def _fallback_why(ctx):
    """There is no untargeted ad here, only a cheaper one.

    With no behavioural signal we still have the device, the clock and the
    timezone, which is enough to place someone in a priced tier. Saying so is
    more honest than pretending the ad is generic.
    """
    ctx = ctx or {}
    bits = []
    if ctx.get("city"):
        bits.append("your connection places you near %s" % ctx["city"])
    if ctx.get("hour") is not None:
        bits.append("it is %02d:00 where you are" % ctx["hour"])
    if ctx.get("device"):
        bits.append("you are on a %s" % ctx["device"])
    if ctx.get("browser"):
        bits.append("running %s" % ctx["browser"])
    if not bits:
        bits = ["you arrived, which is itself a signal"]
    joined = (", ".join(bits[:-1]) + ", and " + bits[-1]) if len(bits) > 1 else bits[0]
    return ("No behavioural profile yet, so this was chosen from context alone: "
            + joined + ". That is still enough to place you in a priced tier.")


def choose(counts, inferences, ctx=None):
    """The single best campaign, with a rationale that is never generic."""
    ranked = sorted(ADS, key=lambda a: _score(a, counts, inferences), reverse=True)
    best = ranked[0]
    best_score = _score(best, counts, inferences)
    if best_score <= 0:
        hour = (ctx or {}).get("hour", 12)
        pool = ([a for a in ADS if a["id"] in ("pizza", "coffee")]
                if (hour >= 22 or hour < 5)
                else [a for a in ADS if a["category"] in
                      ("media", "food", "travel", "footwear")])
        best = dict(random.choice(pool or ADS), why=_fallback_why(ctx))
        best_score = 0.0
    return best, round(best_score, 2)


def pick_many(counts, inferences, n, ctx=None, exclude=()):
    """A slate of distinct campaigns for the in-grid slots, best first."""
    scored = [(_score(a, counts, inferences), a) for a in ADS if a["id"] not in exclude]
    scored.sort(key=lambda t: t[0], reverse=True)

    out, chosen = [], set()
    for score, ad in scored:
        if len(out) >= n:
            break
        if score > 0:
            out.append((dict(ad), round(score, 2)))
            chosen.add(ad["id"])
    if len(out) < n:
        rest = [a for _s, a in scored if a["id"] not in chosen]
        random.shuffle(rest)
        for ad in rest[: n - len(out)]:
            out.append((dict(ad, why=_fallback_why(ctx)), 0.0))
    return out
