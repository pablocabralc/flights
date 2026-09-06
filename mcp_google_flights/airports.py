import csv
from functools import lru_cache
from pathlib import Path

CSV_PATH = Path(__file__).resolve().parent.parent / "enums" / "airports.csv"


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


def search_airports(query: str, limit: int = 8) -> list[dict[str, str]]:
    q = query.strip().lower()
    if not q:
        return []

    scored: list[tuple[int, int, dict[str, str]]] = []
    for i, airport in enumerate(_load()):
        code = airport["code"].lower()
        name = airport["name"].lower()
        city = airport["city"].lower()

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
