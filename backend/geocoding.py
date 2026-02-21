import math
import os
import time
import difflib
from typing import Optional, Tuple, List

import httpx

# Hardcoded coordinates for Kazakhstan cities (lat, lon)
# Used as primary lookup before falling back to 2GIS Geocoder API.
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
    "Карагандинская": (49.8047, 73.1094),
    "Алматинская": (43.2220, 76.8512),
    "Акмолинская": (51.1694, 71.4491),
    "Актюбинская": (50.2797, 57.2070),
    "Атырауская": (47.0945, 51.9236),
    "Восточно-Казахстанская": (49.9481, 82.6278),
    "Жамбылская": (42.9000, 71.3667),
    "Западно-Казахстанская": (51.2333, 51.3667),
    "Костанайская": (53.2141, 63.6246),
    "Кызылординская": (44.8481, 65.5097),
    "Мангистауская": (43.6415, 51.1727),
    "Павлодарская": (52.2979, 76.9673),
    "Северо-Казахстанская": (54.8694, 69.1568),
    "Туркестанская": (43.3000, 68.2667),
    "ЮКО": (42.3417, 69.5901),
    "Mangystau": (43.6415, 51.1727),
    "Абайская": (50.4111, 80.2275),
    "Улытауская": (47.8000, 67.7333),
    "Жетысуская": (45.0167, 78.3667),
    "Семипалатинская": (50.4111, 80.2275),
}

# Coordinates for each office — sourced from 2GIS API (city-level, ru_KZ locale)
OFFICE_COORDS: dict[str, Tuple[float, float]] = {
    "Актау":            (43.6356, 51.1683),
    "Актобе":           (50.3002, 57.1541),
    "Алматы":           (43.2183, 76.8932),
    "Астана":           (51.1295, 71.4431),
    "Атырау":           (47.1180, 51.9706),
    "Караганда":        (49.8156, 73.0833),
    "Кокшетау":         (53.2828, 69.3786),
    "Костанай":         (53.2146, 63.6319),
    "Кызылорда":        (44.8249, 65.5026),
    "Павлодар":         (52.2856, 76.9412),
    "Петропавловск":    (54.8617, 69.1394),
    "Тараз":            (42.8896, 71.3532),
    "Уральск":          (51.2040, 51.3705),
    "Усть-Каменогорск": (49.9482, 82.6280),
    "Шымкент":          (42.3154, 69.5870),
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
# Latin → Cyrillic alias table for Kazakhstan office cities and oblasts.
# Covers the most common romanisation spellings found in ticket data.
# ---------------------------------------------------------------------------
_LATIN_TO_CYRILLIC: dict[str, str] = {
    # Office cities
    "aktau": "Актау",
    "aktobe": "Актобе",
    "aktyubinsk": "Актобе",
    "almaty": "Алматы",
    "alma-ata": "Алматы",
    "almaata": "Алматы",
    "astana": "Астана",
    "nur-sultan": "Астана",
    "nursultan": "Астана",
    "atyrau": "Атырау",
    "karaganda": "Караганда",
    "karagandy": "Караганда",
    "kokshetau": "Кокшетау",
    "kokchetav": "Кокшетау",
    "kostanay": "Костанай",
    "kustanai": "Костанай",
    "kyzylorda": "Кызылорда",
    "pavlodar": "Павлодар",
    "petropavlovsk": "Петропавловск",
    "taraz": "Тараз",
    "zhambyl": "Тараз",
    "uralsk": "Уральск",
    "oral": "Уральск",
    "ust-kamenogorsk": "Усть-Каменогорск",
    "ust kamenogorsk": "Усть-Каменогорск",
    "oskemen": "Усть-Каменогорск",
    "shymkent": "Шымкент",
    "chimkent": "Шымкент",
    "semey": "Семей",
    "semipalatinsk": "Семей",
    # Oblasts / regions
    "akmola": "Акмолинская",
    "akmolinsk": "Акмолинская",
    "aktobe region": "Актюбинская",
    "almaty region": "Алматинская",
    "atyrau region": "Атырауская",
    "east kazakhstan": "Восточно-Казахстанская",
    "zhambyl region": "Жамбылская",
    "west kazakhstan": "Западно-Казахстанская",
    "karaganda region": "Карагандинская",
    "kostanay region": "Костанайская",
    "kyzylorda region": "Кызылординская",
    "mangystau": "Мангистауская",
    "pavlodar region": "Павлодарская",
    "north kazakhstan": "Северо-Казахстанская",
    "turkestan region": "Туркестанская",
    "south kazakhstan": "Туркестанская",
}


def _latin_to_cyrillic(name: str) -> str:
    """Return Cyrillic canonical name if *name* is a known Latin alias, else return as-is."""
    return _LATIN_TO_CYRILLIC.get(name.strip().lower(), name)


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
    Handles Latin-script input via the _LATIN_TO_CYRILLIC alias table.
    """
    if not city_name:
        return None
    city_name = _latin_to_cyrillic(city_name)
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
# 2GIS Geocoder API — street-level geocoding for CIS-style addresses.
# Requires TWOGIS_API_KEY (or DGIS_API_KEY as fallback alias).
# Docs: https://docs.2gis.com/en/api/search/geocoder/reference/3.0/items/geocode
# ---------------------------------------------------------------------------

_TWOGIS_LAST_CALL: float = 0.0
_TWOGIS_MIN_INTERVAL: float = 0.25  # seconds between calls
_TWOGIS_MISSING_KEY_WARNED: bool = False
_TWOGIS_ENDPOINT = "https://catalog.api.2gis.com/3.0/items/geocode"

# Kazakhstan bounding box (approximate)
_KZ_LAT_MIN, _KZ_LAT_MAX = 40.5, 55.5
_KZ_LON_MIN, _KZ_LON_MAX = 50.2, 87.4


def _in_kz_bbox(lat: float, lon: float) -> bool:
    """Return True if coordinates fall within Kazakhstan's bounding box."""
    return _KZ_LAT_MIN <= lat <= _KZ_LAT_MAX and _KZ_LON_MIN <= lon <= _KZ_LON_MAX


def _twogis_geocode(
    query: str,
    near: Optional[Tuple[float, float]] = None,
) -> Optional[Tuple[float, float]]:
    """Call 2GIS geocoder with lightweight rate limiting. Returns (lat, lon) or None."""
    global _TWOGIS_LAST_CALL, _TWOGIS_MISSING_KEY_WARNED

    api_key = (
        os.getenv("TWOGIS_API_KEY")
        or os.getenv("DGIS_API_KEY")
        or ""
    ).strip()
    if not api_key:
        if not _TWOGIS_MISSING_KEY_WARNED:
            print("[Geocoding] 2GIS key missing: set TWOGIS_API_KEY to enable API lookup.")
            _TWOGIS_MISSING_KEY_WARNED = True
        return None

    try:
        elapsed = time.monotonic() - _TWOGIS_LAST_CALL
        if elapsed < _TWOGIS_MIN_INTERVAL:
            time.sleep(_TWOGIS_MIN_INTERVAL - elapsed)

        params = {
            "key": api_key,
            "q": query,
            "fields": "items.point,items.search_attributes",
            "locale": "ru_KZ",
        }
        if near:
            lat, lon = near
            params["point"] = f"{lon},{lat}"
            params["radius"] = 50000

        response = httpx.get(_TWOGIS_ENDPOINT, params=params, timeout=8.0)
        response.raise_for_status()
        _TWOGIS_LAST_CALL = time.monotonic()

        payload = response.json()
        items = payload.get("result", {}).get("items", [])
        if not items:
            return None

        first = items[0]
        point = first.get("point", {})
        lat = point.get("lat")
        lon = point.get("lon")
        if lat is None or lon is None:
            return None

        precision = first.get("search_attributes", {}).get("precision")
        print(
            f"[Geocoding] 2GIS (precision={precision or 'n/a'}): "
            f"'{query}' → ({float(lat):.4f}, {float(lon):.4f})"
        )
        return float(lat), float(lon)
    except Exception as e:
        print(f"[Geocoding] 2GIS error for '{query}': {e}")
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
    Resolve a client location to (lat, lon) using city + region only.
    Street/house are intentionally ignored — 2GIS with locale=ru_KZ
    handles Kazakhstan-specific disambiguation without exact addresses.

    Strategy:
    1. 2GIS: city + region + Казахстан  — primary; ru_KZ locale pins to KZ
       Result validated against KZ bounding box (rejects out-of-KZ hits).
    2. 2GIS: region + Казахстан         — if no city or city lookup failed
       Also bbox-validated.
    3. KZ_CITY_COORDS direct region     — hardcoded fallback (no key / timeout)
    4. KZ_CITY_COORDS fuzzy region      — typo-tolerant hardcoded fallback
    5. Partial substring match on region — last resort
    """
    _ = street, house  # kept for backward compatibility; intentionally unused

    # Normalise Latin-script input to Cyrillic before any lookup
    if city:
        city = _latin_to_cyrillic(city)
    if region:
        region = _latin_to_cyrillic(region)

    # 1. 2GIS — city + region (most precise)
    if city:
        parts = [p for p in [city, region, "Казахстан"] if p]
        coords = _twogis_geocode(", ".join(parts))
        if coords and _in_kz_bbox(*coords):
            return coords
        if coords:
            print(f"[Geocoding] 2GIS result outside KZ bbox for '{', '.join(parts)}' — skipping")

    # 2. 2GIS — region only (if no city, or city lookup failed)
    if region:
        parts = [p for p in [region, "Казахстан"] if p]
        coords = _twogis_geocode(", ".join(parts))
        if coords and _in_kz_bbox(*coords):
            return coords
        if coords:
            print(f"[Geocoding] 2GIS result outside KZ bbox for '{', '.join(parts)}' — skipping")

    # 3. KZ_CITY_COORDS direct region lookup — hardcoded fallback (no API key / timeout)
    if region and region in KZ_CITY_COORDS:
        return KZ_CITY_COORDS[region]

    # 4. KZ_CITY_COORDS fuzzy region lookup — typo-tolerant hardcoded fallback
    if region:
        coords = _fuzzy_city_lookup(region)
        if coords:
            return coords

    # 5. Partial substring match on region — last resort
    if region:
        for key, coords in KZ_CITY_COORDS.items():
            if key.lower() in region.lower() or region.lower() in key.lower():
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
    """
    Return True only when the country field explicitly names a non-KZ country.

    Returns False (treat as domestic) when:
    - country is empty/None  (missing data — fall through to geocoding)
    - country is a recognised KZ spelling ("Казахстан", "Kazakhstan", "KZ", "Қазақстан")

    Any other non-empty value (e.g. "Russia", "UAE") is treated as foreign.
    KZ city/region names mistakenly placed in the country field are handled
    downstream: geocode_client() ignores the country field and uses only
    city/region, so those tickets still route correctly.
    """
    if not country:
        return False
    kz_variants = {"казахстан", "kazakhstan", "kz", "қазақстан"}
    return country.strip().lower() not in kz_variants
