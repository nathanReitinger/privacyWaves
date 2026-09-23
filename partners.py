"""The recipient register.

Article 13(1)(e) requires the "recipients or categories of recipients" of
personal data. The EDPB's transparency guidelines (WP260 rev.01, endorsed by
the EDPB in 2018) say the default should be actual named recipients, and that
a controller falling back on categories must still give the type of recipient
by reference to what it does, plus the industry, sector, sub-sector and
location. The CJEU pushed the same way in C-154/21 RW v Österreichische Post
(12 January 2023): under Article 15 it is the data subject who chooses whether
to be told the names or only the categories.

So v2 names them, one row each, with what they get and why. v1 gives the
category treatment that the ICO called insufficient in its 2023 TikTok notice:
a vague count, no names, no locations.

`shares` is what triggers the disclosure: a partner only appears in the live
"who is receiving this" panel once the purpose it belongs to is switched on.
"""

# role: controller | processor | joint
RECIPIENTS = [
    {
        "name": "Adzumi DSP Ltd",
        "role": "controller",
        "sector": "Advertising technology — demand-side platform",
        "location": "Dublin, Ireland (EEA)",
        "receives": "Pseudonymous device identifier, interest segments, "
                    "the ad slots you were shown",
        "purpose": "Selecting and measuring advertising",
        "basis": "Art. 6(1)(a) consent",
        "transfer": "None. Data stays in the EEA.",
        "retention": "13 months",
        "notice": "https://example.invalid/adzumi/privacy",
        "shares": "ads",
    },
    {
        "name": "NorthBeam Audiences Inc.",
        "role": "controller",
        "sector": "Advertising technology — audience segments",
        "location": "Boston, United States",
        "receives": "Interest and life-stage segments derived from your browsing. "
                    "No name, email or address.",
        "purpose": "Building and selling audience segments",
        "basis": "Art. 6(1)(a) consent",
        "transfer": "United States, under the EU–US Data Privacy Framework; "
                    "standard contractual clauses (2021/914) as a fallback",
        "retention": "13 months",
        "notice": "https://example.invalid/northbeam/privacy",
        "shares": "share",
    },
    {
        "name": "Pelham & Roe Analytics LLP",
        "role": "processor",
        "sector": "Web analytics",
        "location": "Bristol, United Kingdom",
        "receives": "Page views, collection views, search terms, session duration",
        "purpose": "Aggregate usage statistics on our instructions only",
        "basis": "Art. 6(1)(a) consent",
        "transfer": "United Kingdom, under the UK adequacy decision",
        "retention": "14 months, then aggregated beyond re-identification",
        "notice": "https://example.invalid/pelhamroe/privacy",
        "shares": "analytics",
    },
    {
        "name": "Sandmere Hosting B.V.",
        "role": "processor",
        "sector": "Infrastructure and hosting",
        "location": "Amsterdam, Netherlands (EEA)",
        "receives": "Everything, incidentally, as the servers this runs on",
        "purpose": "Running the site",
        "basis": "Art. 6(1)(b) contract and Art. 6(1)(f) legitimate interest",
        "transfer": "None. Data stays in the EEA.",
        "retention": "Same as the underlying record",
        "notice": "https://example.invalid/sandmere/privacy",
        "shares": "necessary",
    },
    {
        "name": "Quillon Mail Relay GmbH",
        "role": "processor",
        "sector": "Transactional email delivery",
        "location": "Frankfurt, Germany (EEA)",
        "receives": "Your email address and order reference, at the point you order",
        "purpose": "Sending your order confirmation",
        "basis": "Art. 6(1)(b) contract",
        "transfer": "None. Data stays in the EEA.",
        "retention": "30 days after delivery",
        "notice": "https://example.invalid/quillon/privacy",
        "shares": "necessary",
    },
    {
        "name": "Veridia Risk Signals Pte Ltd",
        "role": "processor",
        "sector": "Fraud and payment risk scoring",
        "location": "Singapore",
        "receives": "Device fingerprint, IP address, order value",
        "purpose": "Detecting fraudulent orders",
        "basis": "Art. 6(1)(f) legitimate interest — preventing payment fraud. "
                 "Our balancing assessment is available on request.",
        "transfer": "Singapore, under standard contractual clauses (2021/914) "
                    "with a transfer impact assessment on file",
        "retention": "24 months",
        "notice": "https://example.invalid/veridia/privacy",
        "shares": "necessary",
    },
]

# Advertisers whose creative can appear. They are not recipients unless you
# click: an impression is served by us, and only a click hands anything over.
ADVERTISER_NOTE = (
    "Advertisers whose creative may be shown to you do not receive your "
    "personal data when an ad is merely displayed. If you click one, the "
    "advertiser receives the fact of the click, your IP address and your "
    "browser's user agent, because that is inherent in following a link."
)

CATEGORY_FALLBACK = [
    ("Advertising technology", "Demand-side platforms and audience providers",
     "EEA and United States", "2 named above"),
    ("Analytics", "Web measurement processors", "United Kingdom", "1 named above"),
    ("Infrastructure", "Hosting, email delivery, fraud scoring",
     "EEA and Singapore", "3 named above"),
]


def for_consent(consent, version):
    """Who is actually receiving anything, given the choices in force."""
    if version == 1:
        return list(RECIPIENTS)
    out = []
    for r in RECIPIENTS:
        key = r["shares"]
        if key == "necessary" or (consent or {}).get(key):
            out.append(r)
    return out


def names(consent=None, version=2):
    return [r["name"] for r in for_consent(consent, version)]
