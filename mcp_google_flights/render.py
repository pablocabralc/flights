import html
from datetime import date, datetime
from typing import Any

from fast_flights.model import CarbonEmission, Flights, SimpleDatetime, SingleFlight

MONTHS_PT = (
    "jan",
    "fev",
    "mar",
    "abr",
    "mai",
    "jun",
    "jul",
    "ago",
    "set",
    "out",
    "nov",
    "dez",
)
WEEKDAYS_PT = ("seg", "ter", "qua", "qui", "sex", "sáb", "dom")
CURRENCY_SYMBOLS = {"BRL": "R$ ", "USD": "US$ ", "EUR": "€ ", "GBP": "£ "}
SEAT_LABELS_PT = {
    "economy": "Econômica",
    "premium-economy": "Econômica Premium",
    "business": "Executiva",
    "first": "Primeira Classe",
}


def fmt_duration(minutes: int) -> str:
    minutes = max(int(minutes), 0)
    hours, mins = divmod(minutes, 60)
    if hours == 0:
        return f"{mins}min"
    if mins == 0:
        return f"{hours}h"
    return f"{hours}h {mins:02d}min"


def fmt_time(time: tuple[int, int]) -> str:
    return f"{time[0]:02d}:{time[1]:02d}"


def fmt_date(ymd: tuple[int, int, int]) -> str:
    _, month, day = ymd
    return f"{day:02d} {MONTHS_PT[month - 1]}"


def fmt_weekday_date(ymd: tuple[int, int, int]) -> str:
    return f"{WEEKDAYS_PT[date(*ymd).weekday()]}, {fmt_date(ymd)}"


def fmt_price(price: int, currency: str) -> str:
    symbol = CURRENCY_SYMBOLS.get(currency.upper(), f"{currency} " if currency else "")
    return symbol + f"{price:,}".replace(",", ".")


def fmt_co2_abs(grams: int) -> str:
    return f"{grams / 1000:.0f} kg CO₂e"


def fmt_co2_delta(carbon: CarbonEmission | None) -> tuple[str, str] | None:
    if carbon is None or not carbon.typical_on_route or not carbon.emission:
        return None
    delta = round((carbon.emission - carbon.typical_on_route) / carbon.typical_on_route * 100)
    if delta == 0:
        return "na média", "co2--neutral"
    if delta < 0:
        return f"−{abs(delta)}% CO₂e", "co2--good"
    if delta <= 15:
        return f"+{delta}% CO₂e", "co2--bad"
    return f"+{delta}% CO₂e", "co2--worse"


def iso_datetime(dt: SimpleDatetime) -> str:
    y, m, d = dt.date
    h, mi = dt.time
    return f"{y:04d}-{m:02d}-{d:02d}T{h:02d}:{mi:02d}"


def _to_datetime(dt: SimpleDatetime) -> datetime:
    return datetime(*dt.date, *dt.time)


def _total_duration(flight: Flights) -> int:
    legs = flight.flights
    if not legs:
        return 0
    try:
        delta = _to_datetime(legs[-1].arrival) - _to_datetime(legs[0].departure)
        minutes = int(delta.total_seconds() // 60)
        if minutes > 0:
            return minutes
    except (TypeError, ValueError):
        pass
    return sum(leg.duration for leg in legs)


def _day_offset(first: SingleFlight, last: SingleFlight) -> int:
    try:
        return (date(*last.arrival.date) - date(*first.departure.date)).days
    except (TypeError, ValueError):
        return 0


def _airlines_label(flight: Flights) -> str:
    if flight.airlines:
        if flight.type == "multi" or len(flight.airlines) > 1:
            return " + ".join(dict.fromkeys(flight.airlines))
        return flight.airlines[0]
    return flight.type or "—"


def _stops_info(flight: Flights) -> tuple[int, list[str]]:
    legs = flight.flights
    stops = max(len(legs) - 1, 0)
    return stops, [leg.to_airport.code for leg in legs[:-1]]


def render_badge_stops(flight: Flights) -> str:
    stops, connections = _stops_info(flight)
    if stops == 0:
        return '<span class="badge badge--direct">Direto</span>'
    label = "1 parada" if stops == 1 else f"{stops} paradas"
    codes = ", ".join(html.escape(code) for code in connections if code)
    text = f"{label} · {codes}" if codes else label
    return f'<span class="badge badge--stops">{text}</span>'


def _end(airport_code: str, airport_name: str, dt: SimpleDatetime, plus_days: int, arrival: bool) -> str:
    side = "arr" if arrival else "dep"
    sup = ""
    if arrival and plus_days >= 1:
        sup = (
            f'<sup class="leg__plusday" aria-label="chega {plus_days} dia(s) depois">'
            f"+{plus_days}</sup>"
        )
    name_html = (
        f'<span class="leg__airport">{html.escape(airport_name)}</span>' if airport_name else ""
    )
    return (
        f'<div class="leg__end leg__end--{side}">'
        f'<time class="leg__time" datetime="{iso_datetime(dt)}">{fmt_time(dt.time)}{sup}</time>'
        f'<span class="leg__code">{html.escape(airport_code)}</span>'
        f"{name_html}"
        f"</div>"
    )


def render_leg(flight: Flights) -> str:
    legs = flight.flights
    if not legs:
        return ""
    first, last = legs[0], legs[-1]
    plus_days = _day_offset(first, last)
    return (
        '<section class="leg">'
        f'<h3 class="leg__label">{html.escape(fmt_weekday_date(first.departure.date))}</h3>'
        '<div class="leg__route">'
        + _end(first.from_airport.code, first.from_airport.name, first.departure, 0, False)
        + '<div class="leg__middle">'
        f'<span class="leg__duration">{fmt_duration(_total_duration(flight))}</span>'
        '<span class="leg__line" aria-hidden="true"></span>'
        f"{render_badge_stops(flight)}"
        "</div>"
        + _end(last.to_airport.code, last.to_airport.name, last.arrival, plus_days, True)
        + "</div></section>"
    )


def render_segments(flight: Flights) -> str:
    legs = flight.flights
    if len(legs) <= 1:
        return ""

    items: list[str] = []
    for i, leg in enumerate(legs):
        meta_parts = []
        if leg.plane_type:
            meta_parts.append(html.escape(leg.plane_type))
        meta_parts.append(fmt_duration(leg.duration))
        items.append(
            '<li class="seg">'
            f'<span class="seg__times">{fmt_time(leg.departure.time)} '
            f"{html.escape(leg.from_airport.code)} → {fmt_time(leg.arrival.time)} "
            f"{html.escape(leg.to_airport.code)}</span>"
            f'<span class="seg__meta">{" · ".join(meta_parts)}</span>'
            "</li>"
        )
        if i + 1 < len(legs):
            try:
                gap = int(
                    (_to_datetime(legs[i + 1].departure) - _to_datetime(leg.arrival)).total_seconds()
                    // 60
                )
            except (TypeError, ValueError):
                gap = 0
            if gap > 0:
                items.append(
                    f'<li class="seg seg--layover">Conexão em '
                    f"{html.escape(leg.to_airport.code)} · {fmt_duration(gap)}</li>"
                )

    return (
        '<details class="segments"><summary>Detalhes dos trechos</summary>'
        f'<ul class="segments__list">{"".join(items)}</ul></details>'
    )


def render_co2(carbon: CarbonEmission | None) -> str:
    parts: list[str] = []
    delta = fmt_co2_delta(carbon)
    if delta is not None:
        text, css = delta
        parts.append(f'<span class="badge co2 {css}">{text}</span>')
    if carbon is not None and carbon.emission and carbon.emission > 0:
        parts.append(f'<span class="co2__abs">{fmt_co2_abs(carbon.emission)}</span>')
    return "".join(parts)


def _aria_label(flight: Flights, index: int, is_cheapest: bool, currency: str) -> str:
    stops, _ = _stops_info(flight)
    stops_text = "direto" if stops == 0 else ("1 parada" if stops == 1 else f"{stops} paradas")
    prefix = f"Opção {index + 1}" + (", mais barata" if is_cheapest else "")
    return f"{prefix}: {_airlines_label(flight)}, {fmt_price(flight.price, currency)}, {stops_text}"


def render_card(flight: Flights, index: int, is_cheapest: bool, query_summary: dict[str, Any]) -> str:
    currency = query_summary.get("currency") or ""
    passengers = int(query_summary.get("passengers") or 1)
    price_note = (
        "total, 1 passageiro" if passengers == 1 else f"total, {passengers} passageiros"
    )
    cheapest_badge = (
        '<span class="badge badge--cheapest">Mais barato</span>' if is_cheapest else ""
    )
    return (
        "<li>"
        f'<article class="card{" card--cheapest" if is_cheapest else ""}" '
        f'aria-label="{html.escape(_aria_label(flight, index, is_cheapest, currency))}">'
        '<div class="card__main">'
        '<div class="card__top">'
        f"{cheapest_badge}"
        f'<span class="card__airlines">{html.escape(_airlines_label(flight))}</span>'
        "</div>"
        f"{render_leg(flight)}"
        f"{render_segments(flight)}"
        "</div>"
        '<aside class="card__price">'
        f'<span class="price__value">{fmt_price(flight.price, currency)}</span>'
        f'<span class="price__note">{price_note}</span>'
        f"{render_co2(flight.carbon)}"
        "</aside>"
        "</article></li>"
    )


def _render_header(flights: list[Flights], query_summary: dict[str, Any]) -> str:
    origin_code = str(query_summary.get("origin_code") or "")
    dest_code = str(query_summary.get("dest_code") or "")
    origin_name = str(query_summary.get("origin_name") or "")
    dest_name = str(query_summary.get("dest_name") or "")
    trip_type = query_summary.get("trip_type") or "one-way"
    is_round_trip = trip_type == "round-trip"
    depart_date = query_summary.get("depart_date")
    return_date = query_summary.get("return_date")
    passengers = int(query_summary.get("passengers") or 1)
    currency = str(query_summary.get("currency") or "")
    seat_label = SEAT_LABELS_PT.get(
        str(query_summary.get("seat_class") or "economy"), str(query_summary.get("seat_class") or "")
    )

    dates = fmt_weekday_date(tuple(depart_date)) if depart_date else ""
    if is_round_trip and return_date:
        dates += f" (volta {fmt_weekday_date(tuple(return_date))})"

    meta_parts = [p for p in (dates, seat_label) if p]
    meta_parts.append("1 passageiro" if passengers == 1 else f"{passengers} passageiros")
    if currency:
        meta_parts.append(currency)

    airports_line = ""
    if origin_name or dest_name:
        airports_line = (
            f'<p class="header__airports">{html.escape(origin_name or origin_code)} → '
            f"{html.escape(dest_name or dest_code)}</p>"
        )

    count = len(flights)
    count_line = (
        f'<p class="header__count">{count} '
        f'{"opção" if count == 1 else "opções"} · ordenadas por preço</p>'
        if count
        else ""
    )

    note = ""
    if is_round_trip:
        note = (
            '<p class="header__note">Os preços consideram a busca de ida e volta '
            "configurada; os trechos detalhados abaixo mostram a opção de ida retornada "
            "pelo Google Flights.</p>"
        )

    return (
        '<header class="header">'
        '<div class="header__route">'
        '<span class="header__plane" aria-hidden="true">✈</span>'
        f"<h1>{html.escape(origin_code)} "
        f'<span class="header__arrow">→</span> {html.escape(dest_code)}</h1>'
        f'<span class="chip">{"ida e volta" if is_round_trip else "somente ida"}</span>'
        "</div>"
        f"{airports_line}"
        f'<p class="header__meta">{html.escape(" · ".join(meta_parts))}</p>'
        f"{count_line}"
        f"{note}"
        "</header>"
    )


def _render_empty(query_summary: dict[str, Any]) -> str:
    origin = str(query_summary.get("origin_code") or "origem")
    dest = str(query_summary.get("dest_code") or "destino")
    depart_date = query_summary.get("depart_date")
    when = f" em {fmt_date(tuple(depart_date))}" if depart_date else ""
    return (
        '<div class="empty">'
        '<span class="empty__icon" aria-hidden="true">✈</span>'
        "<h2>Nenhum voo encontrado</h2>"
        f"<p>Não encontramos voos de {html.escape(origin)} para {html.escape(dest)}"
        f"{html.escape(when)}. Tente outras datas ou aeroportos próximos.</p>"
        "</div>"
    )


CSS = """
:root{
  --bg:#eef4f6; --surface:#fff; --surface-alt:#f4f8fa;
  --text:#132b36; --text-muted:#5a7382; --border:#d7e3e9;
  --accent:#0e7490; --accent-soft:#e0f2f7;
  --success:#1a7f43; --success-bg:#ddf3e4;
  --warn:#96570a;  --warn-bg:#fdeed3;
  --danger:#b02a2a; --danger-bg:#fde3e3;
  --radius:14px; --shadow:0 1px 3px rgba(19,43,54,.08);
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --bg:#0b1418; --surface:#132630; --surface-alt:#0f1e26;
    --text:#e7eef2; --text-muted:#94aab6; --border:#26424f;
    --accent:#38cde5; --accent-soft:#123742;
    --success:#5fdc94; --success-bg:#11341f;
    --warn:#f0b25e;  --warn-bg:#3a2a10;
    --danger:#f58c8c; --danger-bg:#3a1515;
    --shadow:none;
  }
}
:root[data-theme="dark"]{
  --bg:#0b1418; --surface:#132630; --surface-alt:#0f1e26;
  --text:#e7eef2; --text-muted:#94aab6; --border:#26424f;
  --accent:#38cde5; --accent-soft:#123742;
  --success:#5fdc94; --success-bg:#11341f;
  --warn:#f0b25e;  --warn-bg:#3a2a10;
  --danger:#f58c8c; --danger-bg:#3a1515;
  --shadow:none;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
  font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Ubuntu,"Helvetica Neue",Arial,sans-serif;
  -webkit-text-size-adjust:100%}
.page{max-width:960px;margin:0 auto;padding:20px 16px 40px}
.header{background:var(--surface);border:1px solid var(--border);
  border-radius:var(--radius);padding:20px 24px;box-shadow:var(--shadow)}
.header__route{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.header__route h1{margin:0;font-size:1.5rem;letter-spacing:.02em}
.header__arrow{color:var(--accent)}
.chip{font-size:.8125rem;font-weight:600;color:var(--accent);
  background:var(--accent-soft);border-radius:999px;padding:3px 10px}
.header__airports{margin:4px 0 0;color:var(--text-muted)}
.header__meta{margin:8px 0 0;font-size:.9375rem}
.header__count{margin:2px 0 0;font-size:.8125rem;color:var(--text-muted)}
.header__note{margin:8px 0 0;font-size:.8125rem;color:var(--text-muted);font-style:italic}
.results{list-style:none;margin:20px 0 0;padding:0;display:grid;gap:16px}
@media (min-width:1100px){
  .results{grid-template-columns:1fr 1fr}
  .results > li:first-child{grid-column:1 / -1}
}
.card{display:flex;flex-direction:column;height:100%;
  background:var(--surface);border:1px solid var(--border);
  border-radius:var(--radius);box-shadow:var(--shadow);overflow:hidden}
.card--cheapest{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent),var(--shadow)}
.card__main{padding:16px 20px;flex:1}
.card__top{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:10px}
.card__airlines{font-weight:600;font-size:.9375rem}
.card__price{border-top:1.5px dashed var(--border);padding:14px 20px;
  display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
@media (min-width:640px){
  .card{flex-direction:row}
  .card__price{border-top:0;border-left:1.5px dashed var(--border);
    flex-direction:column;align-items:flex-end;justify-content:center;
    gap:4px;min-width:160px;text-align:right}
}
.price__value{font-size:1.75rem;font-weight:700;color:var(--accent);font-variant-numeric:tabular-nums}
.price__note{font-size:.8125rem;color:var(--text-muted)}
.co2__abs{font-size:.8125rem;color:var(--text-muted)}
.leg{padding:10px 0}
.leg__label{margin:0 0 6px;font-size:.75rem;font-weight:700;
  letter-spacing:.08em;text-transform:uppercase;color:var(--text-muted)}
.leg__route{display:grid;grid-template-columns:1fr auto 1fr;gap:12px;align-items:start}
.leg__end{display:flex;flex-direction:column;min-width:0}
.leg__end--arr{text-align:right;align-items:flex-end}
.leg__time{font-size:1.25rem;font-weight:600;font-variant-numeric:tabular-nums}
.leg__plusday{font-size:.6875rem;color:var(--warn);font-weight:700}
.leg__code{font-weight:600;font-size:.875rem;letter-spacing:.04em}
.leg__airport{font-size:.8125rem;color:var(--text-muted);
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:100%}
.leg__middle{display:flex;flex-direction:column;align-items:center;gap:4px;padding-top:4px;min-width:110px}
.leg__duration{font-size:.8125rem;color:var(--text-muted)}
.leg__line{width:100%;height:2px;background:var(--border);position:relative}
.leg__line::after{content:"";position:absolute;right:-1px;top:-3px;
  border:4px solid transparent;border-left:6px solid var(--border)}
.badge{display:inline-flex;align-items:center;font-size:.75rem;font-weight:700;
  border-radius:999px;padding:2px 10px;white-space:nowrap}
.badge--cheapest{background:var(--accent-soft);color:var(--accent);text-transform:uppercase;letter-spacing:.06em}
.badge--direct{background:var(--success-bg);color:var(--success)}
.badge--stops{background:var(--warn-bg);color:var(--warn)}
.co2--good{background:var(--success-bg);color:var(--success)}
.co2--bad{background:var(--warn-bg);color:var(--warn)}
.co2--worse{background:var(--danger-bg);color:var(--danger)}
.co2--neutral{background:var(--surface-alt);color:var(--text-muted);border:1px solid var(--border)}
.segments{margin-top:8px;font-size:.875rem}
.segments summary{cursor:pointer;color:var(--accent);font-weight:600;font-size:.8125rem}
.segments__list{list-style:none;margin:8px 0 0;padding:10px 12px;
  background:var(--surface-alt);border-radius:8px;display:grid;gap:6px}
.seg{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}
.seg__meta{color:var(--text-muted)}
.seg--layover{color:var(--text-muted);font-size:.8125rem;font-style:italic}
.empty{background:var(--surface);border:1px dashed var(--border);
  border-radius:var(--radius);margin-top:20px;padding:48px 24px;
  text-align:center;color:var(--text-muted)}
.empty h2{color:var(--text);margin:12px 0 4px}
.empty p{margin:0;max-width:40ch;margin-inline:auto}
.footer{margin-top:24px;font-size:.8125rem;color:var(--text-muted);text-align:center}
""".strip()


def render_html(flights: list[Flights], query_summary: dict[str, Any]) -> str:
    ordered = sorted(flights, key=lambda f: f.price)
    show_cheapest_badge = len(ordered) > 1

    if ordered:
        cards = "".join(
            render_card(flight, i, show_cheapest_badge and i == 0, query_summary)
            for i, flight in enumerate(ordered)
        )
        body = f'<ol class="results">{cards}</ol>'
    else:
        body = _render_empty(query_summary)

    fetched_at = query_summary.get("fetched_at") or datetime.now()
    timestamp = fetched_at.strftime("%d/%m/%Y %H:%M")

    origin_code = html.escape(str(query_summary.get("origin_code") or ""))
    dest_code = html.escape(str(query_summary.get("dest_code") or ""))

    return (
        "<!DOCTYPE html>"
        '<html lang="pt-BR"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>Voos {origin_code} → {dest_code}</title>"
        f"<style>{CSS}</style></head><body>"
        '<div class="page">'
        f"{_render_header(ordered, query_summary)}"
        f"{body}"
        f'<footer class="footer">Preços obtidos do Google Flights em {timestamp} '
        "e sujeitos a alteração. Emissões comparadas à média da rota.</footer>"
        "</div></body></html>"
    )
