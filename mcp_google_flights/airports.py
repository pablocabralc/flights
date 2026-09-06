import csv
import unicodedata
from functools import lru_cache
from pathlib import Path

CSV_PATH = Path(__file__).resolve().parent.parent / "enums" / "airports.csv"

# The dataset only has English place names, but users often search in
# Portuguese. Keys/values are already accent-stripped + lowercased so they
# match the normalized query directly.
CITY_ALIASES_PT_EN = {
    "lisboa": "lisbon",
    "londres": "london",
    "nova york": "new york",
    "nova iorque": "new york",
    "roma": "rome",
    "madri": "madrid",
    "madrid": "madrid",
    "milao": "milan",
    "moscou": "moscow",
    "moscovo": "moscow",
    "pequim": "beijing",
    "toquio": "tokyo",
    "atenas": "athens",
    "varsovia": "warsaw",
    "praga": "prague",
    "viena": "vienna",
    "genebra": "geneva",
    "copenhague": "copenhagen",
    "bruxelas": "brussels",
    "munique": "munich",
    "florenca": "florence",
    "veneza": "venice",
    "napoles": "naples",
    "sevilha": "seville",
    "zurique": "zurich",
    "haia": "the hague",
    "amsterda": "amsterdam",
    "cidade do cabo": "cape town",
    "nova deli": "new delhi",
    "xangai": "shanghai",
    "seul": "seoul",
    "estocolmo": "stockholm",
    "helsinque": "helsinki",
    "belgrado": "belgrade",
    "bucareste": "bucharest",
    "budapeste": "budapest",
    "cidade do mexico": "mexico city",
    "filadelfia": "philadelphia",
    "nova orleans": "new orleans",
    "cairo": "cairo",
    "meca": "mecca",
    "jerusalem": "jerusalem",
    "genova": "genoa",
    "marselha": "marseille",
}


# Multi-airport metro areas. Google Flights natively accepts these pseudo
# "city" IATA codes as from_airport/to_airport and searches every airport in
# the group at once (e.g. "NYC" covers JFK + LGA + EWR) — verified against
# the shipped enums/airports.csv, whose `city_code` column defines the same
# groupings. Keys are accent-stripped + lowercased (PT and EN names).
METRO_NAME_TO_CODE = {
    "new york": "NYC",
    "nova york": "NYC",
    "nova iorque": "NYC",
    "london": "LON",
    "londres": "LON",
    "paris": "PAR",
    "chicago": "CHI",
    "washington": "WAS",
    "washington dc": "WAS",
    "moscow": "MOW",
    "moscou": "MOW",
    "moscovo": "MOW",
    "rome": "ROM",
    "roma": "ROM",
    "milan": "MIL",
    "milao": "MIL",
    "buenos aires": "BUE",
    "rio de janeiro": "RIO",
    "sao paulo": "SAO",
    "osaka": "OSA",
    "seoul": "SEL",
    "seul": "SEL",
    "beijing": "BJS",
    "pequim": "BJS",
    "shanghai": "SHA",
    "xangai": "SHA",
    "toronto": "YTO",
    "montreal": "YMQ",
    "stockholm": "STO",
    "estocolmo": "STO",
    "istanbul": "IST",
    "tokyo": "TYO",
    "toquio": "TYO",
    "berlin": "BER",
    "frankfurt": "FRA",
    "bangkok": "BKK",
    "jakarta": "JKT",
    "dubai": "DXB",
    "bucharest": "BUH",
    "bucareste": "BUH",
    "warsaw": "WAW",
    "varsovia": "WAW",
    "los angeles": "LAX",
    "mexico city": "MEX",
    "cidade do mexico": "MEX",
    "sapporo": "SPK",
}


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


@lru_cache(maxsize=1)
def _load() -> list[dict[str, str]]:
    with CSV_PATH.open(encoding="utf-8", newline="") as f:
        rows = []
        for row in csv.DictReader(f):
            code = (row.get("code") or "").strip()
            name = (row.get("name") or "").strip()
            if not code or not name:
                continue
            rows.append(
                {
                    "code": code,
                    "name": name,
                    "city": (row.get("city") or "").strip(),
                    "country": (row.get("country_id") or "").strip(),
                    "city_code": (row.get("city_code") or "").strip(),
                    "icao": (row.get("icao") or "").strip(),
                }
            )
        return rows


@lru_cache(maxsize=1)
def _metro_groups() -> dict[str, list[dict[str, str]]]:
    """city_code -> member airports, for city_codes shared by 2+ airports."""
    groups: dict[str, list[dict[str, str]]] = {}
    for airport in _load():
        city_code = airport["city_code"]
        if city_code:
            groups.setdefault(city_code, []).append(airport)
    return {code: members for code, members in groups.items() if len(members) > 1}


def _metro_members(city_code: str, limit: int) -> list[dict[str, str]]:
    members = _metro_groups().get(city_code, [])
    # Real commercial airports carry an ICAO code; heliports/ferry/seaplane
    # stops sharing the same metro grouping don't. Drop them whenever the
    # group has at least one real airport, so e.g. "New York" surfaces
    # JFK/LGA/EWR instead of Manhattan heliports.
    with_icao = [a for a in members if a["icao"]]
    ranked = with_icao or members
    return [{**a, "metro_code": city_code} for a in ranked[:limit]]


def _match(q: str, limit: int) -> list[dict[str, str]]:
    scored: list[tuple[int, int, dict[str, str]]] = []
    for i, airport in enumerate(_load()):
        code = _strip_accents(airport["code"]).lower()
        name = _strip_accents(airport["name"]).lower()
        city = _strip_accents(airport["city"]).lower()

        if code == q:
            rank = 0
        elif name.startswith(q) or (city and city.startswith(q)):
            rank = 1
        elif q in code or q in name or (city and q in city):
            rank = 2
        else:
            continue

        scored.append((rank, i, airport))

    scored.sort(key=lambda item: (item[0], item[1]))
    return [airport for _, _, airport in scored[:limit]]


def _drop_internal_fields(airports: list[dict[str, str]]) -> list[dict[str, str]]:
    return [{k: v for k, v in a.items() if k != "icao"} for a in airports]


def search_airports(query: str, limit: int = 8) -> list[dict[str, str]]:
    q = _strip_accents(query.strip().lower())
    if not q:
        return []

    # A place name (or its metro pseudo-code, e.g. "NYC") that groups several
    # airports: return the whole cluster right away instead of whichever
    # single airport happens to match the query text, since boroughs/suburb
    # names (JFK's is "Inwood") rarely contain the metro's common name.
    metro_code = METRO_NAME_TO_CODE.get(q) or (q.upper() if q.upper() in _metro_groups() else None)
    if metro_code:
        return _drop_internal_fields(_metro_members(metro_code, limit))

    results = _match(q, limit)
    if not results and q in CITY_ALIASES_PT_EN:
        # The dataset only has English place names (e.g. "Lisbon", not
        # "Lisboa"); retry with the known English equivalent.
        results = _match(CITY_ALIASES_PT_EN[q], limit)
    return _drop_internal_fields(results)
