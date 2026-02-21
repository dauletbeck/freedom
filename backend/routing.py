import re
from typing import List, Optional, Tuple
from models import Manager
from geocoding import (
    geocode_client, find_sorted_offices,
    fuzzy_office_city, CITY_TO_OFFICES, is_foreign,
)

# Global round-robin counters
_rr_counters: dict[str, int] = {}
_foreign_counter: list[int] = [0]  # mutable int for 50/50 Astana/Almaty split

# Distance threshold (km) within which two offices are considered "equidistant"
# and tie-breaking by manager load applies.
EQUIDISTANT_THRESHOLD_KM = 50.0

# Explicit abroad-location hints in ticket text.
# Used for UI guidance only; routing remains governed by core rules.
FOREIGN_LOCATION_HINTS = [
    "за границ",
    "в другой стране",
    "не в казахстане",
    "нахожусь не в казахстане",
    "outside kazakhstan",
    "abroad",
    "overseas",
]
FOREIGN_COUNTRY_ALIASES = [
    "росси", "russia",
    "турци", "turkey",
    "оаэ", "uae", "emirates", "dubai", "дуба",
    "сша", "usa", "united states", "america",
    "канада", "canada",
    "герман", "germany",
    "великобрит", "united kingdom", "uk",
    "кыргыз", "kyrgyz",
    "узбекистан", "uzbekistan",
    "таджикистан", "tajikistan",
    "азербайджан", "azerbaijan",
    "грузи", "georgia",
    "армени", "armenia",
    "кита", "china",
    "коре", "korea",
    "япони", "japan",
]
CURRENT_LOCATION_PATTERN = re.compile(
    r"(?:нахожусь|сейчас|временно|пребываю|currently|temporarily|right now)"
    r"(?:\s+\w+){0,3}\s+(?:в|in)\s+([^\n,.;:!?]{2,40})",
    flags=re.IGNORECASE,
)
KAZAKHSTAN_TOKENS = ("казахстан", "қазақстан", "kazakhstan")


def reset_counters():
    """Reset all routing counters (call before each pipeline run)."""
    _rr_counters.clear()
    _foreign_counter[0] = 0


def build_rr_key(
    office: str,
    is_vip: bool,
    is_data_change: bool,
    language: str,
    needs_senior: bool,
) -> str:
    """
    Build a stable Round Robin key that reflects the *eligibility pool*, not
    the individual ticket values.  Two tickets that end up competing for the
    same pool of managers must share the same key so their counter advances
    together.

    Parameters are the boolean eligibility flags, not raw field values:
    - is_vip        : segment is VIP or Priority
    - is_data_change: ticket_type is "Смена данных"
    - language      : "KZ" | "ENG" | "RU"  (only KZ/ENG add a filter)
    - needs_senior  : sentiment is Негативный (soft senior preference active)
    """
    lang = language if language in ("KZ", "ENG") else "RU"
    return f"{office}|vip={is_vip}|data={is_data_change}|lang={lang}|senior={needs_senior}"


def _office_load(managers: List[Manager], office: str) -> int:
    return sum(m.current_load for m in managers if m.office == office)


def has_explicit_foreign_location(description: Optional[str]) -> bool:
    """
    Detect whether the client explicitly states they are currently abroad.
    This is intentionally conservative: it only triggers on explicit hints.
    """
    if not description:
        return False

    text = description.lower()
    if any(hint in text for hint in FOREIGN_LOCATION_HINTS):
        return True

    for match in CURRENT_LOCATION_PATTERN.finditer(text):
        location = match.group(1).strip()
        if any(token in location for token in KAZAKHSTAN_TOKENS):
            continue
        if any(alias in location for alias in FOREIGN_COUNTRY_ALIASES):
            return True

    return False


def get_target_office(
    country: Optional[str],
    city: Optional[str],
    region: Optional[str],
    street: Optional[str] = None,
    house: Optional[str] = None,
    managers: Optional[List[Manager]] = None,
) -> Tuple[str, Optional[float], Optional[float]]:
    """
    Determine the target office and client coordinates.
    Returns (office_name, client_lat, client_lon).

    Selection strategy:
    1. Explicitly foreign country → 50/50 Астана / Алматы
       (missing/empty country falls through to geocoding, not this branch)
    2. City maps to exactly ONE office (direct or fuzzy match) →
       assign that office immediately; no distance calculation.
    3. Otherwise →
       geocode to precise coordinates, then:
       a. If the nearest two offices are within EQUIDISTANT_THRESHOLD_KM →
          tie-break by total manager load (lower load wins).
       b. Otherwise → nearest office by Haversine.
    """
    foreign = is_foreign(country)

    # Explicitly foreign country → split 50/50 Астана/Алматы immediately.
    # Missing/empty country is NOT treated as foreign — we still try geocoding
    # by city/region, and only fall back to Астана/Алматы if that also fails.
    if foreign:
        idx = _foreign_counter[0] % 2
        _foreign_counter[0] += 1
        return ("Астана" if idx == 0 else "Алматы"), None, None

    # --- Single-office shortcut ------------------------------------------------
    # If the client's city fuzzy-matches to a city that has exactly one office,
    # we can skip coordinate lookup entirely.
    if city:
        matched_office = fuzzy_office_city(city)
        if matched_office:
            offices_in_city = CITY_TO_OFFICES.get(matched_office.strip().lower(), [])
            if len(offices_in_city) == 1:
                # Fetch coords for DB storage (instant dict lookup, no API call)
                from geocoding import KZ_CITY_COORDS
                coords = KZ_CITY_COORDS.get(matched_office)
                lat, lon = coords if coords else (None, None)
                return matched_office, lat, lon

    # --- Coordinate-based selection (precise or multi-office) ----------------
    coords = geocode_client(city, region, country)

    if coords is None:
        idx = _foreign_counter[0] % 2
        _foreign_counter[0] += 1
        return ("Астана" if idx == 0 else "Алматы"), None, None

    lat, lon = coords
    sorted_offices = find_sorted_offices(lat, lon)

    if managers is not None and len(sorted_offices) >= 2:
        dist1, office1 = sorted_offices[0]
        dist2, office2 = sorted_offices[1]
        if dist2 - dist1 <= EQUIDISTANT_THRESHOLD_KM:
            # Equidistant → pick office with lower manager load
            office = office1 if _office_load(managers, office1) <= _office_load(managers, office2) else office2
            return office, lat, lon

    return sorted_offices[0][1], lat, lon


def filter_managers(
    managers: List[Manager],
    office: Optional[str],
    segment: str,
    ticket_type: str,
    language: str,
    sentiment: str = "Нейтральный",
    limit: Optional[int] = 2,
) -> List[Manager]:
    """
    Apply skill/competency filters to managers at the target office.
    Returns top-2 eligible managers sorted by load ascending.

    Hard filters (all must pass):
    - VIP/Priority segment → manager must have VIP skill
    - Смена данных          → manager must be Главный специалист
    - KZ language           → manager must have KZ skill
    - ENG language          → manager must have ENG skill

    Soft preference (applied after hard filters, before top-2 selection):
    - Негативный sentiment  → prefer Ведущий специалист or Главный специалист
      Falls through to the full eligible pool if no senior is available.
    """
    if office:
        pool = [m for m in managers if m.office == office]
    else:
        pool = [m for m in managers if m.office]

    # Hard filter: VIP or Priority segment
    if segment in ("VIP", "Priority"):
        pool = [m for m in pool if m.skills and "VIP" in m.skills]

    # Hard filter: Смена данных → Главный специалист only
    if ticket_type == "Смена данных":
        pool = [m for m in pool if m.position and "Главный специалист" in m.position]

    # Hard filter: language skills
    if language == "KZ":
        pool = [m for m in pool if m.skills and "KZ" in m.skills]
    elif language == "ENG":
        pool = [m for m in pool if m.skills and "ENG" in m.skills]

    # Sort full eligible pool by load ascending before applying soft rules
    pool.sort(key=lambda m: m.current_load)

    # Soft preference: negative sentiment → prefer senior managers
    if sentiment == "Негативный":
        senior_pool = [
            m for m in pool
            if m.position and any(
                p in m.position for p in ("Ведущий специалист", "Главный специалист")
            )
        ]
        if senior_pool:
            pool = senior_pool

    if limit is None:
        return pool
    return pool[:limit]


def assign_manager(
    eligible: List[Manager],
    rr_key: str,
) -> Tuple[Optional[Manager], int]:
    """
    Round-robin assign from eligible managers.
    Returns (manager, rr_index).
    """
    if not eligible:
        return None, 0

    current = _rr_counters.get(rr_key, 0)
    idx = current % len(eligible)
    _rr_counters[rr_key] = current + 1

    return eligible[idx], idx


def route_ticket(
    managers: List[Manager],
    country: Optional[str],
    city: Optional[str],
    region: Optional[str],
    segment: str,
    ticket_type: str,
    language: str,
    sentiment: str = "Нейтральный",
    street: Optional[str] = None,
    house: Optional[str] = None,
) -> Tuple[Optional[Manager], str, Optional[float], Optional[float], int]:
    """
    Full routing pipeline for a single ticket.
    Returns (assigned_manager, office, client_lat, client_lon, rr_index).

    If no eligible managers exist at nearest office, falls back to Астана then Алматы.
    """
    office, lat, lon = get_target_office(
        country, city, region,
        street=street, house=house,
        managers=managers,
    )

    eligible = filter_managers(managers, office, segment, ticket_type, language, sentiment)

    # Fallback: if no eligible at nearest office, try Астана then Алматы
    fallback_offices = ["Астана", "Алматы"]
    fallback_idx = 0
    while not eligible and fallback_idx < len(fallback_offices):
        fallback = fallback_offices[fallback_idx]
        if fallback != office:
            eligible = filter_managers(managers, fallback, segment, ticket_type, language, sentiment)
            if eligible:
                office = fallback
        fallback_idx += 1

    # Build RR key from eligibility flags (not raw ticket values).
    # All tickets with the same eligibility constraints share one counter,
    # so the round-robin alternates correctly within each logical pool.
    is_vip = segment in ("VIP", "Priority")
    is_data_change = ticket_type == "Смена данных"
    needs_senior = sentiment == "Негативный"
    rr_key = build_rr_key(office, is_vip, is_data_change, language, needs_senior)
    manager, rr_index = assign_manager(eligible, rr_key)

    return manager, office, lat, lon, rr_index
