import math
import time
import difflib
import ssl
from typing import Optional, Tuple, List

# macOS ships without trusted root certs for Python — create a permissive SSL context
# so Nominatim HTTPS requests don't fail with CERTIFICATE_VERIFY_FAILED.
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

# Hardcoded coordinates for Kazakhstan cities (lat, lon)
# Used as primary lookup before falling back to Nominatim
KZ_CITY_COORDS: dict[str, Tuple[float, float]] = {
    "Алматы": (43.2220, 76.8512),
    "Астана": (51.1694, 71.4491),
    "Нур-Султан": (51.1694, 71.4491),
    "Шымкент": (42.3417, 69.5901),
    "Усть-Каменогорск": (49.9481, 82.6278),
    "Семей": (50.4111, 80.2275),
    "Актобе": (50.2797, 57.2070),
    "Тараз": (42.9000, 71.3667),
    "Павлодар": (52.2979, 76.9673),
    "Атырау": (47.0945, 51.9236),
    "Костанай": (53.2141, 63.6246),
    "Кызылорда": (44.8481, 65.5097),
    "Уральск": (51.2333, 51.3667),
    "Петропавловск": (54.8694, 69.1568),
    "Актау": (43.6415, 51.1727),
    "Темиртау": (50.0597, 72.9594),
    "Туркестан": (43.3000, 68.2667),
    "Кокшетау": (53.2837, 69.3921),
    "Талдыкорган": (45.0167, 78.3667),
    "Экибастуз": (51.7167, 75.3333),
    "Рудный": (52.9667, 63.1167),
    "Жезказган": (47.8000, 67.7333),
    "Балхаш": (46.8500, 74.9833),
    "Аксу": (52.0350, 76.9025),
    "Жанаозен": (43.3333, 52.8667),
    "Сарань": (49.8167, 72.8833),
    "Шахтинск": (49.7167, 72.6000),
    "Аркалык": (50.2500, 66.9167),
    "Кентау": (43.5167, 68.5000),
    "Ленгер": (42.1667, 69.8833),
    "Бадам": (42.2667, 70.0000),
    "Шардара": (41.2667, 68.0667),
    "Тургень": (43.5000, 77.5000),
    "Красный Яр": (51.5000, 70.5000),
    "Кокпекты": (49.0333, 81.1333),
    "Осакаровка": (50.1000, 72.5333),
    "Шортанды": (51.6833, 71.0167),
    "Индербор": (48.5500, 51.8000),
    "Конаев": (43.8667, 77.0667),
    "Капчагай": (43.8667, 77.0667),
    "Кокпек": (43.8000, 78.0000),
    "Бескарагай": (51.5000, 81.5000),
    "Косшы": (51.1833, 71.6500),
    "Кыргауылды": (43.6833, 76.9000),
    "Бейнеу": (45.2667, 55.1333),
    "Жаркент": (44.1667, 80.0000),
    "Откалык": (43.5500, 68.3000),
    "Степногорск": (52.3500, 71.8833),
    "Каратау": (43.1833, 70.4667),
    "Каскелен": (43.1983, 76.6217),
    "Талгар": (43.3000, 77.2667),
    "Есик": (43.3500, 77.4333),
    "Кандыагаш": (49.4667, 57.4333),
    "Лисаковск": (52.5500, 62.5000),
    "Байконур": (45.6200, 63.3028),
    "Жетысай": (40.7667, 68.3333),
    "Казалинск": (45.7667, 62.1000),
    "Аральск": (46.7833, 61.6667),
    "Кызылжар": (54.8694, 69.1568),
    "Курчатов": (50.7333, 78.5333),
    "Каражал": (47.9167, 70.8000),
    "Сатпаев": (47.9000, 67.5333),
    "Приозёрск": (46.0833, 73.9333),
    "Каратобе": (50.6167, 60.0000),
    "Хромтау": (50.2500, 58.4500),
    "Шалкар": (47.8333, 59.6000),
    "Кандагач": (49.4667, 57.4333),
    "Эмба": (48.8333, 58.1500),
    "Жем": (48.0500, 56.4667),
    "Курган": (54.8694, 69.1568),
    "Тобыл": (53.2141, 63.6246),
    "Магнитогорск": (53.2141, 63.6246),
    "Бурабай": (53.0667, 70.2500),
    "Щучинск": (52.9333, 70.2000),
    "Кокшетау": (53.2837, 69.3921),
    "Карагандинская": (49.8047, 73.1094),
    "Алматинская": (43.2220, 76.8512),
    "Акмолинская": (51.1694, 71.4491),
    "Актюбинская": (50.2797, 57.2070),
    "Атырауская": (47.0945, 51.9236),
    "Восточно-Казахстанская": (49.9481, 82.6278),
    "Жамбылская": (42.9000, 71.3667),
    "Западно-Казахстанская": (51.2333, 51.3667),
    "Карагандинская": (49.8047, 73.1094),
    "Костанайская": (53.2141, 63.6246),
    "Кызылординская": (44.8481, 65.5097),
    "Мангистауская": (43.6415, 51.1727),
    "Павлодарская": (52.2979, 76.9673),
    "Северо-Казахстанская": (54.8694, 69.1568),
    "Туркестанская": (43.3000, 68.2667),
    "ЮКО": (42.3417, 69.5901),
    "Мангистауская": (43.6415, 51.1727),
    "Mangystau": (43.6415, 51.1727),
    "Актобе": (50.2797, 57.2070),
    "Абайская": (50.4111, 80.2275),
    "Улытауская": (47.8000, 67.7333),
    "Жетысуская": (45.0167, 78.3667),
    "Семипалатинская": (50.4111, 80.2275),
    "Павлодар": (52.2979, 76.9673),
    "Актау": (43.6415, 51.1727),
    "Бейнеу": (45.2667, 55.1333),
}

# Coordinates for each office
OFFICE_COORDS: dict[str, Tuple[float, float]] = {
    "Актау": (43.6415, 51.1727),
    "Актобе": (50.2797, 57.2070),
    "Алматы": (43.2220, 76.8512),
    "Астана": (51.1694, 71.4491),
    "Атырау": (47.0945, 51.9236),
    "Караганда": (49.8047, 73.1094),
    "Кокшетау": (53.2837, 69.3921),
    "Костанай": (53.2141, 63.6246),
    "Кызылорда": (44.8481, 65.5097),
    "Павлодар": (52.2979, 76.9673),
    "Петропавловск": (54.8694, 69.1568),
    "Тараз": (42.9000, 71.3667),
    "Уральск": (51.2333, 51.3667),
    "Усть-Каменогорск": (49.9481, 82.6278),
    "Шымкент": (42.3417, 69.5901),
}


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance in km between two coordinates."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------------------------------------------------------------------
# CITY_TO_OFFICES: maps a normalised city name → list of office names.
# In the current dataset each city has exactly one office; this mapping lets
# routing.py short-circuit to that office without a distance calculation, and
# is ready for future datasets where a city may have multiple branches.
# ---------------------------------------------------------------------------
CITY_TO_OFFICES: dict[str, List[str]] = {}
for _office_name in OFFICE_COORDS:
    _key = _office_name.strip().lower()
    CITY_TO_OFFICES.setdefault(_key, []).append(_office_name)


# ---------------------------------------------------------------------------
# Fuzzy matching
# ---------------------------------------------------------------------------

def _fuzzy_city_lookup(name: str) -> Optional[Tuple[float, float]]:
    """
    Typo-tolerant city lookup using difflib (no external calls).
    cutoff=0.75 catches 1–2 character errors reliably.
    """
    matches = difflib.get_close_matches(name, KZ_CITY_COORDS.keys(), n=1, cutoff=0.75)
    if matches:
        print(f"[Geocoding] Fuzzy matched '{name}' → '{matches[0]}'")
        return KZ_CITY_COORDS[matches[0]]
    return None


def fuzzy_office_city(city_name: str) -> Optional[str]:
    """
    Return the canonical office-city name that best fuzzy-matches *city_name*.
    Used by routing to resolve which office city the client belongs to.
    """
    if not city_name:
        return None
    norm = city_name.strip().lower()
    # Exact match first
    if norm in CITY_TO_OFFICES:
        offices = CITY_TO_OFFICES[norm]
        return offices[0] if len(offices) == 1 else None  # ambiguous → None
    # Fuzzy match against office city names
    matches = difflib.get_close_matches(city_name, OFFICE_COORDS.keys(), n=1, cutoff=0.75)
    if matches:
        print(f"[Geocoding] Fuzzy office match '{city_name}' → '{matches[0]}'")
        return matches[0]
    return None


# ---------------------------------------------------------------------------
# Nominatim (OpenStreetMap) — street-level geocoding, free, no API key
# Rate limit: ≤1 req/sec per OSM usage policy
# ---------------------------------------------------------------------------

_NOM_LAST_CALL: float = 0.0
_NOM_MIN_INTERVAL: float = 1.1  # seconds between calls


def _nominatim_geocode(query: str) -> Optional[Tuple[float, float]]:
    """Call Nominatim with built-in rate limiting. Returns (lat, lon) or None."""
    global _NOM_LAST_CALL
    try:
        from geopy.geocoders import Nominatim
        from geopy.exc import GeocoderTimedOut, GeocoderUnavailable

        elapsed = time.monotonic() - _NOM_LAST_CALL
        if elapsed < _NOM_MIN_INTERVAL:
            time.sleep(_NOM_MIN_INTERVAL - elapsed)

        geocoder = Nominatim(user_agent="fire-routing/1.0", ssl_context=_SSL_CTX)
        location = geocoder.geocode(query, language="ru", timeout=6)
        _NOM_LAST_CALL = time.monotonic()

        if location:
            print(f"[Geocoding] Nominatim: '{query}' → ({location.latitude:.4f}, {location.longitude:.4f})")
            return (location.latitude, location.longitude)
    except Exception as e:
        print(f"[Geocoding] Nominatim error for '{query}': {e}")
    return None


# ---------------------------------------------------------------------------
# Public geocoding entry point
# ---------------------------------------------------------------------------

def geocode_client(
    city: Optional[str],
    region: Optional[str],
    country: Optional[str],
    street: Optional[str] = None,
    house: Optional[str] = None,
) -> Optional[Tuple[float, float]]:
    """
    Resolve a client address to (lat, lon) using a multi-tier strategy:

    1. Full street address via Nominatim  ← most precise; only if street given
    2. City-only via Nominatim            ← if city isn't in hardcoded map
    3. Direct lookup in KZ_CITY_COORDS   ← instant; covers all known KZ cities
    4. Fuzzy city lookup                 ← handles typos (1-2 char errors)
    5. Direct region lookup              ← fallback to region centroid
    6. Fuzzy region lookup
    7. Partial substring match           ← legacy catch-all
    """
    # 1. Street-level Nominatim (most precise when street is available)
    if street:
        parts = [p for p in [street, house, city, region, "Казахстан"] if p]
        coords = _nominatim_geocode(", ".join(parts))
        if coords:
            return coords

    # 2. Direct city lookup
    if city and city in KZ_CITY_COORDS:
        return KZ_CITY_COORDS[city]

    # 3. Direct region lookup
    if region and region in KZ_CITY_COORDS:
        return KZ_CITY_COORDS[region]

    # 4. Fuzzy city lookup (typo-tolerant)
    if city:
        coords = _fuzzy_city_lookup(city)
        if coords:
            return coords

    # 5. Fuzzy region lookup
    if region:
        coords = _fuzzy_city_lookup(region)
        if coords:
            return coords

    # 6. City-only Nominatim (unknown city not in hardcoded map)
    if city:
        parts = [p for p in [city, region, "Казахстан"] if p]
        coords = _nominatim_geocode(", ".join(parts))
        if coords:
            return coords

    # 7. Partial substring match (legacy fallback)
    for candidate in [city, region]:
        if not candidate:
            continue
        for key, coords in KZ_CITY_COORDS.items():
            if key.lower() in candidate.lower() or candidate.lower() in key.lower():
                return coords

    return None


def find_nearest_office(client_lat: float, client_lon: float) -> str:
    """Return the name of the nearest office to the given coordinates."""
    nearest = min(
        OFFICE_COORDS.items(),
        key=lambda kv: haversine(client_lat, client_lon, kv[1][0], kv[1][1]),
    )
    return nearest[0]


def find_sorted_offices(client_lat: float, client_lon: float) -> list:
    """Return all offices sorted by distance ascending: list of (distance_km, office_name)."""
    return sorted(
        (haversine(client_lat, client_lon, lat, lon), name)
        for name, (lat, lon) in OFFICE_COORDS.items()
    )


def is_foreign(country: Optional[str]) -> bool:
    """Return True if the client is not from Kazakhstan."""
    if not country:
        return False
    kz_variants = {"казахстан", "kazakhstan", "kz", "қазақстан"}
    return country.strip().lower() not in kz_variants
