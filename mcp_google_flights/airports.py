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
                }
            )
        return rows


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


def search_airports(query: str, limit: int = 8) -> list[dict[str, str]]:
    q = _strip_accents(query.strip().lower())
    if not q:
        return []

    results = _match(q, limit)
    if not results and q in CITY_ALIASES_PT_EN:
        # The dataset only has English place names (e.g. "Lisbon", not
        # "Lisboa"); retry with the known English equivalent.
        results = _match(CITY_ALIASES_PT_EN[q], limit)
    return results
