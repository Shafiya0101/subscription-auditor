"""
The two agent tools.

TOOL 1  resolve_merchant(raw_descriptor)      -> clean brand + category
TOOL 2  detect_recurring_charges(transactions) -> recurring subs + annual cost

Both are DETERMINISTIC on purpose. The LLM orchestrates and narrates, but every
number the user sees is computed here from their real data -- never guessed by the
model. That grounding is the whole point of the project (chatbot guesses, agent verifies).
"""
from __future__ import annotations
import re
import statistics
from collections import defaultdict
from datetime import datetime
from dateutil import parser as dateparser

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def _parse_date(value):
    """ISO (YYYY-MM-DD) -> dayfirst=False; everything else -> dayfirst=True (EU default)."""
    if isinstance(value, datetime):
        return value
    s = str(value).strip()
    dayfirst = not bool(_ISO_DATE.match(s))
    return dateparser.parse(s, dayfirst=dayfirst)


# ---------------------------------------------------------------------------
# TOOL 1 : merchant-name resolver
# ---------------------------------------------------------------------------
# Curated map of the cryptic descriptors banks print -> (brand, category).
# Keys are matched as substrings against an UPPERCASED, cleaned descriptor.
# International + French merchants (this is a French course, so both matter).
_MERCHANT_DB: list[tuple[str, str, str]] = [
    # streaming video
    ("NETFLIX", "Netflix", "streaming_video"),
    ("DISNEY", "Disney+", "streaming_video"),
    ("DISNEYPLUS", "Disney+", "streaming_video"),
    ("PRIMEVIDEO", "Amazon Prime Video", "streaming_video"),
    ("CANAL+", "Canal+", "streaming_video"),
    ("CANALPLUS", "Canal+", "streaming_video"),
    ("MOLOTOV", "Molotov", "streaming_video"),
    ("PARAMOUNT", "Paramount+", "streaming_video"),
    ("MAX.COM", "Max", "streaming_video"),
    ("HBO", "Max", "streaming_video"),
    # music
    ("SPOTIFY", "Spotify", "music"),
    ("DEEZER", "Deezer", "music"),
    ("APPLE.COM/BILL", "Apple", "apple_services"),
    ("APPLEMUSIC", "Apple Music", "music"),
    ("YOUTUBEPREMIUM", "YouTube Premium", "music"),
    ("YOUTUBE", "YouTube Premium", "music"),
    ("AUDIBLE", "Audible", "audiobooks"),
    # cloud / productivity / software
    ("SQSP", "Squarespace", "software"),
    ("SQUARESPACE", "Squarespace", "software"),
    ("ADOBE", "Adobe", "software"),
    ("NOTION", "Notion", "software"),
    ("DROPBOX", "Dropbox", "cloud_storage"),
    ("GOOGLE*", "Google", "cloud_storage"),
    ("GOOGLE STORAGE", "Google One", "cloud_storage"),
    ("GOOGLE ONE", "Google One", "cloud_storage"),
    ("ICLOUD", "Apple iCloud", "cloud_storage"),
    ("MSFT", "Microsoft", "software"),
    ("MICROSOFT", "Microsoft", "software"),
    ("GITHUB", "GitHub", "software"),
    ("OPENAI", "OpenAI", "software"),
    ("CHATGPT", "OpenAI", "software"),
    ("ANTHROPIC", "Anthropic", "software"),
    ("CLAUDE.AI", "Anthropic", "software"),
    ("CANVA", "Canva", "software"),
    ("LINKEDIN", "LinkedIn", "software"),
    ("PATREON", "Patreon", "membership"),
    ("SUBSTACK", "Substack", "membership"),
    # shopping memberships
    ("AMZNPRIME", "Amazon Prime", "shopping_membership"),
    ("AMAZON PRIME", "Amazon Prime", "shopping_membership"),
    ("PRIME MEMBER", "Amazon Prime", "shopping_membership"),
    # gaming
    ("PLAYSTATION", "PlayStation Plus", "gaming"),
    ("PSN", "PlayStation Plus", "gaming"),
    ("XBOX", "Xbox Game Pass", "gaming"),
    ("NINTENDO", "Nintendo Switch Online", "gaming"),
    # fitness
    ("BASIC-FIT", "Basic-Fit", "fitness"),
    ("BASICFIT", "Basic-Fit", "fitness"),
    ("STRAVA", "Strava", "fitness"),
    # french telecom / transport / utilities
    ("SFR", "SFR", "telecom"),
    ("ORANGE", "Orange", "telecom"),
    ("BOUYGUES", "Bouygues Telecom", "telecom"),
    ("FREE MOBILE", "Free Mobile", "telecom"),
    ("FREE TELECOM", "Free", "telecom"),
    ("NAVIGO", "Navigo (IDFM)", "transport"),
    ("IDFM", "Navigo (IDFM)", "transport"),
    # misc
    ("LINKEDIN PREMIUM", "LinkedIn Premium", "software"),
    ("NORDVPN", "NordVPN", "software"),
    ("EXPRESSVPN", "ExpressVPN", "software"),
    ("1PASSWORD", "1Password", "software"),
]

# tokens/patterns to strip so "SQSP*ABC123 4258" -> "SQSP"
_NOISE = re.compile(
    r"""(
        \b\d{2,}\b            # long digit runs (ref numbers)
        | \*[A-Z0-9]+         # *XYZ123 tails
        | \#[A-Z0-9]+
        | \b[A-Z]{2}\d{2,}\b  # ref codes
        | \bPAR\b|\bLON\b|\bLONDON\b|\bDUBLIN\b|\bIE\b|\bUS\b|\bFR\b|\bGB\b  # city/country tails
        | \bCARD\b|\bPAYMENT\b|\bPMT\b|\bVISA\b|\bDEBIT\b|\bRECURRING\b|\bPURCHASE\b
        | \bWWW\.|\.COM\b|\.FR\b|\.IO\b|\.NET\b
    )""",
    re.VERBOSE,
)


def _clean(descriptor: str) -> str:
    up = descriptor.upper().strip()
    up = _NOISE.sub(" ", up)
    up = re.sub(r"[^A-Z0-9+&/. -]", " ", up)
    up = re.sub(r"\s+", " ", up).strip()
    return up


def resolve_merchant(raw_descriptor: str) -> dict:
    """TOOL 1. Turn a cryptic bank descriptor into a clean brand + category.

    Returns {brand, category, known}. If we can't confidently match it we set
    known=False and return the cleaned string -- the agent is instructed NEVER
    to invent a brand for an unknown descriptor (guardrail).
    """
    cleaned = _clean(raw_descriptor)
    haystack = raw_descriptor.upper()
    for needle, brand, category in _MERCHANT_DB:
        if needle in haystack or needle in cleaned:
            return {"brand": brand, "category": category, "known": True}
    # fall back to a tidied version of the raw text, flagged as unknown
    pretty = cleaned.title() if cleaned else raw_descriptor.strip()
    return {"brand": pretty or "Unknown", "category": "unknown", "known": False}


# ---------------------------------------------------------------------------
# TOOL 2 : recurring-charge detection
# ---------------------------------------------------------------------------
def _cadence_from_days(days: float) -> tuple[str, float]:
    """Map a median inter-charge interval to a named cadence + periods/year."""
    buckets = [
        (6, 8, "weekly", 52),
        (12, 16, "biweekly", 26),
        (26, 35, "monthly", 12),
        (55, 70, "bi-monthly", 6),
        (85, 100, "quarterly", 4),
        (170, 195, "semi-annual", 2),
        (350, 385, "annual", 1),
    ]
    for lo, hi, name, ppy in buckets:
        if lo <= days <= hi:
            return name, ppy
    # not a clean cadence -> approximate from the interval
    ppy = round(365.0 / days, 2) if days > 0 else 0
    return "irregular", ppy


def _amounts_consistent(amounts: list[float], tol_pct: float) -> bool:
    """Recurring subs are stable-ish but CAN step up on a price change. So we don't
    require every charge to match -- we require that MOST charges cluster around the
    median (distinguishing a subscription from variable spend like groceries)."""
    if len(amounts) < 2:
        return True
    med = statistics.median(amounts)
    if med == 0:
        return False
    tol = max(med * tol_pct / 100.0, 1.0)
    near = sum(1 for a in amounts if abs(a - med) <= tol)
    if near / len(amounts) >= 0.6:  # 60%+ cluster -> looks like a subscription
        return True
    # otherwise reject only if amounts swing wildly (variable merchant)
    cv = statistics.pstdev(amounts) / med
    return cv <= 0.15


def detect_recurring_charges(transactions: list[dict], amount_tolerance_pct: float = 8.0) -> dict:
    """TOOL 2. Find recurring charges and annualise their cost.

    transactions: [{date, description, amount, merchant?, category?}]
      - amount is a positive number = money leaving the account.
      - if 'merchant'/'category' are absent they are resolved here.

    Returns a structured report: subscriptions[], totals, review_flags.
    Only merchants actually present in `transactions` can ever appear in output.
    """
    # normalise + group
    groups: dict[str, list[dict]] = defaultdict(list)
    meta: dict[str, dict] = {}
    raw_descriptors: dict[str, set] = defaultdict(set)
    for t in transactions:
        desc = str(t.get("description", "")).strip()
        info = {"brand": t.get("merchant"), "category": t.get("category"), "known": None}
        if not info["brand"]:
            info = resolve_merchant(desc)
        key = info["brand"].upper()
        meta[key] = info
        raw_descriptors[key].add(desc)
        try:
            amt = abs(float(t["amount"]))
        except (KeyError, TypeError, ValueError):
            continue
        try:
            d = _parse_date(t["date"])
        except (KeyError, ValueError, TypeError, OverflowError):
            d = None
        groups[key].append({"date": d, "amount": amt, "description": desc})

    subscriptions = []
    for key, items in groups.items():
        dated = sorted([i for i in items if i["date"] is not None], key=lambda x: x["date"])
        amounts = [i["amount"] for i in items]
        info = meta[key]

        if len(dated) >= 2:
            intervals = [(dated[i + 1]["date"] - dated[i]["date"]).days for i in range(len(dated) - 1)]
            intervals = [d for d in intervals if d > 0]
            if not intervals:
                continue
            med_interval = statistics.median(intervals)
            cadence, ppy = _cadence_from_days(med_interval)
            consistent_amt = _amounts_consistent(amounts, amount_tolerance_pct)
            regular = cadence != "irregular"
            if not (consistent_amt and regular):
                continue  # not confidently recurring
            med_amount = round(statistics.median(amounts), 2)
            annual = round(med_amount * ppy, 2)
            monthly = round(annual / 12.0, 2)
            subscriptions.append({
                "merchant": info["brand"],
                "category": info["category"],
                "known_merchant": bool(info.get("known", False)),
                "amount_per_charge": med_amount,
                "cadence": cadence,
                "charges_seen": len(items),
                "monthly_cost": monthly,
                "annual_cost": annual,
                "confidence": "high",
                "last_seen": dated[-1]["date"].date().isoformat(),
                "source_descriptors": sorted(raw_descriptors[key]),
            })
        elif len(items) == 1 and info.get("known") and info.get("category") not in ("transport",):
            # single charge from a merchant that is typically a subscription
            amt = round(amounts[0], 2)
            subscriptions.append({
                "merchant": info["brand"],
                "category": info["category"],
                "known_merchant": True,
                "amount_per_charge": amt,
                "cadence": "unknown (1 charge seen)",
                "charges_seen": 1,
                "monthly_cost": None,
                "annual_cost": None,
                "confidence": "low",
                "last_seen": (dated[-1]["date"].date().isoformat() if dated else None),
                "source_descriptors": sorted(raw_descriptors[key]),
            })

    subscriptions.sort(key=lambda s: (s["annual_cost"] or 0), reverse=True)

    confirmed = [s for s in subscriptions if s["confidence"] == "high"]
    total_annual = round(sum(s["annual_cost"] for s in confirmed), 2)
    total_monthly = round(sum(s["monthly_cost"] for s in confirmed), 2)

    # ---- review flags (honest heuristics, not certainty) -------------------
    flags = []
    by_cat: dict[str, list[str]] = defaultdict(list)
    for s in confirmed:
        by_cat[s["category"]].append(s["merchant"])
    for cat, brands in by_cat.items():
        if cat in ("streaming_video", "music", "cloud_storage") and len(brands) >= 2:
            flags.append({
                "type": "overlapping_services",
                "message": f"{len(brands)} {cat.replace('_', ' ')} subscriptions: {', '.join(brands)}. Do you use all of them?",
            })
    for s in confirmed:
        if s["monthly_cost"] is not None and s["monthly_cost"] < 15:
            flags.append({
                "type": "easy_to_forget",
                "message": f"{s['merchant']} is only {s['monthly_cost']}/mo -- small charges like this are the easiest to forget ({s['annual_cost']}/yr).",
            })
        if s["cadence"] == "annual":
            flags.append({
                "type": "annual_renewal",
                "message": f"{s['merchant']} renews once a year ({s['annual_cost']}/yr) -- easy to miss the renewal date.",
            })
    for s in subscriptions:
        if s["confidence"] == "low":
            flags.append({
                "type": "single_charge",
                "message": f"Only one {s['merchant']} charge in this window ({s['amount_per_charge']}). Could be a new sub, a trial that just converted, or a one-off.",
            })

    return {
        "subscriptions": subscriptions,
        "totals": {
            "confirmed_count": len(confirmed),
            "monthly_recurring": total_monthly,
            "annual_recurring": total_annual,
        },
        "review_flags": flags,
    }
