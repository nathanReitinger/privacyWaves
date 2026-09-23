"""Narration.

The browser reports signals as bare keys and values. The sentences are written
here, on the server, so what you read in the feed is what the server decided to
say about you rather than something the page made up locally. That distinction
matters: the commentary is not a flourish in the interface, it is the log.

Each entry is (template, tier). Tier drives the colour in the feed:

    0  mundane      things any site sees
    1  behavioural  how you move and hesitate
    2  hardware     what your machine gave away
    3  intimate     what it implies about you
"""

TEMPLATES = {
    # ---- arrival -------------------------------------------------------
    "visit.new":            ("New subject has entered. Welcome.", 0),
    "visit.returning":      ("Subject has been here before. Visit number {v}.", 3),
    "visit.hour":           ("Subject is browsing at {v}.", 0),
    "visit.workday":        ("Subject is shopping between nine and five on a working day. "
                             "Either flexible employment or none.", 3),
    "visit.weekend":        ("Subject is browsing at the weekend.", 1),
    "visit.latenight":      ("Subject is awake and shopping at {v}. Noted for the sleep model.", 3),
    "visit.referrer":       ("Subject arrived from {v}.", 1),
    "visit.direct":         ("Subject typed the address directly. No referrer to trade.", 1),

    # ---- pointer -------------------------------------------------------
    "mouse.first":          ("Subject moved the pointer for the first time.", 0),
    "mouse.up":             ("Subject has moved up.", 0),
    "mouse.down":           ("Subject has moved down.", 0),
    "mouse.left":           ("Subject has moved left.", 0),
    "mouse.right":          ("Subject has moved right.", 0),
    "mouse.turn":           ("Subject suddenly changed direction.", 1),
    "mouse.straight10":     ("Subject moved in a straight line for ten pixels.", 1),
    "mouse.straight100":    ("Subject moved in a straight line for one hundred pixels.", 1),
    "mouse.straight500":    ("Subject moved in a straight line for five hundred pixels. "
                             "That is a trackpad flick, not a hand.", 2),
    "mouse.fast":           ("Subject moved quickly: {v}.", 1),
    "mouse.slow":           ("Subject moved slowly: {v}.", 1),
    "mouse.veryslow":       ("Subject is moving very slowly. Reading, or unsure.", 2),
    "mouse.travel1k":       ("Pointer has travelled one thousand pixels.", 0),
    "mouse.travel10k":      ("Pointer has travelled ten thousand pixels this session.", 1),
    "mouse.travel100k":     ("Pointer has travelled one hundred thousand pixels. "
                             "Subject is not browsing, subject is pacing.", 3),
    "mouse.quadrant":       ("Subject spends most time in the {v} of the window.", 2),
    "mouse.tremor":         ("Pointer path shows a fine tremor. This can indicate a trackpad, "
                             "a train, caffeine, or a motor condition. We do not distinguish.", 3),
    "mouse.steady":         ("Pointer path is unusually steady. Probably a mouse, not a trackpad.", 2),
    "mouse.idle10":         ("Subject has not moved for ten seconds.", 1),
    "mouse.idle60":         ("Subject has not moved for a minute. Still logged in, still watched.", 2),
    "mouse.left_window":    ("Pointer left the window. Subject is looking at something else.", 1),
    "mouse.returned":       ("Pointer came back after {v}.", 1),
    "mouse.approach":       ("Subject approaches targets from the {v}. "
                             "Consistent with a {v2}-handed user.", 3),
    "mouse.hover_hesitate": ("Subject hovered over Mint for {v} without clicking. Hesitation logged.", 3),

    # ---- clicks --------------------------------------------------------
    "click.first":          ("First click after {v}. That is {v2} than most.", 2),
    "click.any":            ("Subject clicked.", 0),
    "click.outside":        ("Subject clicked on nothing in particular.", 0),
    "click.double":         ("Subject double-clicked.", 0),
    "click.triple":         ("Subject triple-clicked.", 1),
    "click.right":          ("Subject opened the context menu.", 1),
    "click.right_image":    ("Subject right-clicked an artwork. Probable intent: save the image "
                             "rather than buy the token.", 3),
    "click.drag":           ("Subject dragged something.", 1),
    "click.rate":           ("Subject is clicking {v} times a second.", 2),
    "click.rage":           ("Rapid repeated clicking in one spot. Frustration, or a dead control. "
                             "Either way it is a churn signal.", 3),
    "click.count":          ("Subject has clicked {v} times.", 0),
    "click.precision":      ("Subject's clicks land within {v} of the target centre. Fine motor "
                             "control is good.", 3),

    # ---- keyboard ------------------------------------------------------
    "key.first":            ("Subject started typing.", 0),
    "key.speed":            ("Typing cadence is {v} between keystrokes.", 2),
    "key.backspace":        ("Subject corrected themselves.", 1),
    "key.backspace_many":   ("Subject has made {v} corrections. Hesitant, or typing on a phone.", 2),
    "key.paste":            ("Subject pasted from the clipboard. The value did not come from "
                             "their fingers, so it probably came from a password manager or "
                             "another tab.", 3),
    "key.copy":             ("Subject copied text from this page.", 1),
    "key.cut":              ("Subject cut text.", 1),
    "key.tab":              ("Subject is navigating by keyboard. Possible screen reader or "
                             "motor accessibility need.", 3),
    "key.escape":           ("Subject pressed Escape. Something was unwanted.", 1),
    "key.find":             ("Subject opened find-in-page. Looking for something we did not "
                             "make easy to see.", 3),
    "key.save":             ("Subject tried to save the page.", 2),
    "key.print":            ("Subject tried to print the page.", 2),
    "key.devtools":         ("Subject tried to open developer tools. Technical user. "
                             "Flagged for the fraud model.", 3),
    "key.selectall":        ("Subject selected the whole page.", 1),
    "key.reload":           ("Subject reloaded. We kept everything.", 2),

    # ---- window --------------------------------------------------------
    "win.size":             ("Window is {v}.", 0),
    "win.resize":           ("Subject resized the window.", 1),
    "win.orientation":      ("Window is now {v}.", 1),
    "win.wide":             ("Window is over {v} wide. Large display, likely a desk.", 2),
    "win.narrow":           ("Narrow window. Phone, or a tiled desktop.", 2),
    "win.blur":             ("Subject switched to another window.", 1),
    "win.focus":            ("Subject came back after {v}.", 1),
    "win.away_long":        ("Subject was away for {v}. Long enough to have done something else "
                             "entirely, which we cannot see and would very much like to.", 3),
    "win.scroll_down":      ("Subject scrolled down.", 0),
    "win.scroll_up":        ("Subject scrolled back up. Re-reading something.", 1),
    "win.scroll_depth":     ("Subject reached {v} of the page.", 1),
    "win.scroll_bottom":    ("Subject reached the bottom. Thorough.", 2),
    "win.zoom":             ("Page zoom changed to {v}.", 2),
    "win.fullscreen":       ("Subject went fullscreen.", 1),

    # ---- hardware ------------------------------------------------------
    "dev.cores":            ("Subject's machine has {v} CPU cores.", 2),
    "dev.memory":           ("Subject's machine reports {v} of RAM.", 2),
    "dev.platform":         ("Platform is {v}.", 2),
    "dev.browser":          ("Subject opened this in {v}.", 0),
    "dev.gpu":              ("Graphics hardware is {v}. That string alone narrows the subject "
                             "to a small share of all visitors.", 3),
    "dev.screen":           ("Screen is {v}.", 2),
    "dev.dpr":              ("Display is {v}.", 2),
    "dev.touch":            ("Device reports {v} simultaneous touch points.", 2),
    "dev.pointer":          ("Primary input is a {v}.", 2),
    "dev.battery":          ("Battery is at {v}.", 3),
    "dev.battery_low":      ("Battery is at {v} and not charging. Subject is away from a desk, "
                             "and has a deadline on their attention.", 3),
    "dev.charging":         ("Device started charging.", 2),
    "dev.network":          ("Connection reports as {v}.", 2),
    "dev.savedata":         ("Subject has data saver on. Metered connection, or a careful budget.", 3),
    "dev.rtt":              ("Round trip time is {v}.", 2),
    "dev.timezone":         ("Timezone is {v}.", 2),
    "dev.languages":        ("Accepted languages: {v}. The order is a reasonable guess at "
                             "nationality.", 3),
    "dev.locale":           ("Locale prefers {v}.", 2),
    "dev.clockskew":        ("Subject's clock differs from ours by {v}.", 2),
    "dev.fonts":            ("{v} identifiable fonts installed. The combination is close to "
                             "unique.", 3),
    "dev.canvas":           ("Canvas fingerprint is {v}. It survives clearing cookies.", 3),
    "dev.audio":            ("Audio stack fingerprint is {v}.", 3),
    "dev.cameras":          ("Device has {v}. We cannot see through them, and did not ask to.", 3),
    "dev.permissions":      ("Permission states read without a prompt: {v}.", 3),
    "dev.storage":          ("Browser offers {v} of storage. We have used a fraction of it.", 2),
    "dev.codecs":           ("Media support: {v}. Another few bits of entropy.", 2),
    "dev.darkmode":         ("Subject prefers a {v} interface.", 1),
    "dev.contrast":         ("Subject has requested {v}.", 3),
    "dev.reducedmotion":    ("Subject has reduced motion enabled. Often vestibular sensitivity "
                             "or migraine. This is health data, inferred from a CSS query.", 3),
    "dev.webdriver":        ("Automation flag is set. Subject may be a bot.", 3),
    "dev.plugins":          ("{v} browser plugins enumerated.", 2),
    "dev.dnt":              ("Subject sends a do-not-track signal. {v}", 3),
    "dev.uadata":           ("Browser brand list: {v}.", 2),
    "dev.heap":             ("JavaScript heap limit is {v}.", 2),
    "dev.orientation_sensor": ("Device reports physical tilt. Subject is holding it, at {v}.", 3),

    # ---- what they looked at -------------------------------------------
    "token.hover":          ("Subject lingered on {v}.", 1),
    "token.long":           ("Subject spent {v} on {v2}. That is real interest.", 3),
    "coll.focus":           ("Subject keeps returning to {v}.", 3),
    "search.typed":         ("Subject searched for {v}.", 2),
    "search.empty":         ("Subject searched for {v} and found nothing. The gap in our "
                             "catalogue is now a gap we know they want filled.", 3),
    "sel.text":             ("Subject selected {v} of text.", 1),
    "cart.add":             ("Subject queued {v}.", 1),
    "cart.remove":          ("Subject removed {v}. Reconsidered.", 2),
    "cart.abandon":         ("Subject has left {v} sitting in the cart. Retargeting window opens "
                             "in twenty minutes.", 3),
    "form.focus":           ("Subject focused the {v} field.", 1),
    "form.keystroke":       ("Field {v} now reads: {v2}", 3),
    "form.abandon":         ("Subject started the {v} field and left it unfinished.", 3),
    "tab.rights":           ("Subject opened the rights tab. Privacy-aware. This changes nothing "
                             "about what we collect.", 3),
    "pane.hidden":          ("Subject hid the panel showing what we collect. "
                             "Collection continues.", 3),
    "pane.shown":           ("Subject brought the panel back.", 1),
    "pane.resized":         ("Subject resized the panel to {v}.", 1),
    "a11y.larger":          ("Subject increased the text size to {v}. Possible low vision, "
                             "or a large display, or tired eyes. We will guess the first, "
                             "because it is worth more.", 3),
    "a11y.smaller":         ("Subject reduced the text size to {v}.", 2),
    "rights.used":          ("Subject exercised a right. Logged, with a timestamp, forever.", 3),

    # ---- advertising ---------------------------------------------------
    "ad.shown":             ("Subject was shown {v}. {v2}", 3),
    "ad.clicked":           ("Subject clicked the {v} ad. That click earned us {v2}.", 3),
    "ad.blocked":           ("No targeted ad was served. The house ad earns nothing.", 1),
    "token.opened":         ("Subject opened {v} full size. Close inspection is a stronger "
                             "intent signal than a click.", 3),
    "ad.revenue":           ("Subject has now generated {v} in advertising revenue.", 3),
}

TIER_NAMES = {0: "routine", 1: "behaviour", 2: "device", 3: "inference"}

# Only milestones reach the log. Everything else is still recorded as a signal
# and still appears in the dossier, the export and the access pack — it simply
# does not need a sentence written about it. Narrating every mouse direction
# was accurate and useless.
ALWAYS_LOG = {
    "visit.new", "visit.workday", "visit.weekend", "visit.latenight", "visit.returning",
    "mouse.first", "click.first", "key.first",
    "cart.add", "cart.abandon", "search.typed", "search.empty",
    "ad.shown", "ad.clicked", "ad.blocked", "token.opened",
    "rights.used", "pane.hidden", "tab.rights",
}


def is_milestone(key):
    """Worth a line in the log: anything that reveals or concludes, plus a few firsts."""
    if key in ALWAYS_LOG:
        return True
    _tpl, tier = TEMPLATES.get(key, (None, 0))
    return tier >= 2


def render(key, v=None, v2=None):
    """Turn a signal into a sentence. Unknown keys degrade to the bare key."""
    tpl, tier = TEMPLATES.get(key, (None, 0))
    if tpl is None:
        return ("Subject triggered %s." % key.replace(".", " "), 0)
    try:
        return (tpl.format(v=v if v is not None else "", v2=v2 if v2 is not None else ""), tier)
    except (KeyError, IndexError):
        return (tpl, tier)


def known_keys():
    return sorted(TEMPLATES)
