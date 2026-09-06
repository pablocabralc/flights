from datetime import date, datetime
from typing import Any

from fast_flights import FlightQuery, FlightsNotFound, Passengers, create_query, get_flights
from fast_flights.model import Flights

from .airports import search_airports as _search_airports
from .render import iso_datetime, render_html

try:  # mcp >= 2.0 renamed FastMCP to MCPServer
    from mcp.server.mcpserver import MCPServer as _Server
except ModuleNotFoundError:  # pragma: no cover - mcp 1.x fallback
    from mcp.server.fastmcp import FastMCP as _Server

mcp = _Server(name="google-flights")


def _total_duration(flight: Flights) -> int:
    legs = flight.flights
    if not legs:
        return 0
    start = datetime(*legs[0].departure.date, *legs[0].departure.time)
    end = datetime(*legs[-1].arrival.date, *legs[-1].arrival.time)
    minutes = int((end - start).total_seconds() // 60)
    return minutes if minutes > 0 else sum(leg.duration for leg in legs)


def _serialize(flight: Flights, currency: str) -> dict[str, Any]:
    legs = flight.flights
    carbon = flight.carbon
    emission_kg = round(carbon.emission / 1000, 1) if carbon and carbon.emission else None
    typical_kg = (
        round(carbon.typical_on_route / 1000, 1) if carbon and carbon.typical_on_route else None
    )
    delta_pct = (
        round((carbon.emission - carbon.typical_on_route) / carbon.typical_on_route * 100)
        if carbon and carbon.typical_on_route and carbon.emission
        else None
    )
    return {
        "price": flight.price,
        "currency": currency,
        "airlines": list(flight.airlines),
        "stops": max(len(legs) - 1, 0),
        "connecting_airports": [leg.to_airport.code for leg in legs[:-1]],
        "duration_minutes": _total_duration(flight),
        "departure": iso_datetime(legs[0].departure) if legs else None,
        "arrival": iso_datetime(legs[-1].arrival) if legs else None,
        "plane_types": [leg.plane_type for leg in legs],
        "carbon_emission_kg": emission_kg,
        "carbon_typical_kg": typical_kg,
        "carbon_delta_pct": delta_pct,
    }


def _do_search_flights(
    *,
    from_airport: str,
    to_airport: str,
    departure_date: str,
    return_date: str | None = None,
    seat: str = "economy",
    adults: int = 1,
    children: int = 0,
    infants_in_seat: int = 0,
    infants_on_lap: int = 0,
    max_stops: int | None = None,
    airlines: list[str] | None = None,
    currency: str = "BRL",
    language: str = "pt-BR",
    carry_on_bags: int = 0,
    checked_bags: int = 0,
    max_price: int | None = None,
) -> dict[str, Any]:
    from_airport = from_airport.strip().upper()
    to_airport = to_airport.strip().upper()

    depart_ymd = date.fromisoformat(departure_date)
    return_ymd = date.fromisoformat(return_date) if return_date else None

    legs = [
        FlightQuery(
            date=departure_date,
            from_airport=from_airport,
            to_airport=to_airport,
            max_stops=max_stops,
            airlines=airlines,
        )
    ]
    if return_ymd is not None:
        legs.append(
            FlightQuery(
                date=return_date,
                from_airport=to_airport,
                to_airport=from_airport,
                max_stops=max_stops,
                airlines=airlines,
            )
        )

    query = create_query(
        flights=legs,
        seat=seat,
        trip="round-trip" if return_ymd is not None else "one-way",
        passengers=Passengers(
            adults=adults,
            children=children,
            infants_in_seat=infants_in_seat,
            infants_on_lap=infants_on_lap,
        ),
        language=language,
        currency=currency,
        max_stops=max_stops,
        max_price=max_price,
        carry_on_bags=carry_on_bags,
        checked_bags=checked_bags,
    )

    try:
        results: list[Flights] = sorted(get_flights(query), key=lambda f: f.price)
    except FlightsNotFound:
        results = []

    origin_name = ""
    dest_name = ""
    if results and results[0].flights:
        origin_name = results[0].flights[0].from_airport.name
        dest_name = results[0].flights[-1].to_airport.name

    passenger_count = adults + children + infants_in_seat + infants_on_lap
    query_summary = {
        "origin_code": from_airport,
        "origin_name": origin_name,
        "dest_code": to_airport,
        "dest_name": dest_name,
        "depart_date": (depart_ymd.year, depart_ymd.month, depart_ymd.day),
        "return_date": (
            (return_ymd.year, return_ymd.month, return_ymd.day) if return_ymd else None
        ),
        "trip_type": "round-trip" if return_ymd is not None else "one-way",
        "seat_class": seat,
        "passengers": passenger_count,
        "currency": currency,
        "fetched_at": datetime.now(),
    }

    return {
        "count": len(results),
        "cheapest_price": results[0].price if results else None,
        "currency": currency,
        "query": {
            "from_airport": from_airport,
            "to_airport": to_airport,
            "departure_date": departure_date,
            "return_date": return_date,
            "trip_type": query_summary["trip_type"],
            "seat": seat,
            "passengers": {
                "adults": adults,
                "children": children,
                "infants_in_seat": infants_in_seat,
                "infants_on_lap": infants_on_lap,
                "total": passenger_count,
            },
            "max_stops": max_stops,
            "airlines": airlines,
            "currency": currency,
            "language": language,
            "carry_on_bags": carry_on_bags,
            "checked_bags": checked_bags,
            "max_price": max_price,
        },
        "flights": [_serialize(flight, currency) for flight in results],
        "html": render_html(results, query_summary),
    }


@mcp.tool()
def search_flights(
    from_airport: str,
    to_airport: str,
    departure_date: str,
    return_date: str | None = None,
    seat: str = "economy",
    adults: int = 1,
    children: int = 0,
    infants_in_seat: int = 0,
    infants_on_lap: int = 0,
    max_stops: int | None = None,
    airlines: list[str] | None = None,
    currency: str = "BRL",
    language: str = "pt-BR",
    carry_on_bags: int = 0,
    checked_bags: int = 0,
    max_price: int | None = None,
) -> dict[str, Any]:
    """Busca passagens aéreas no Google Flights e devolve os dados estruturados
    junto de um HTML pronto para apresentar as opções ao usuário.

    Códigos de aeroporto: use SEMPRE o código IATA de 3 letras (ex.: GRU, LIS, JFK).
    Se o usuário informar o nome de uma cidade ou aeroporto ("São Paulo", "Lisboa"),
    chame antes a tool `search_airports` para descobrir o código correto — não
    tente adivinhar.

    Datas: formato ISO "YYYY-MM-DD" (ex.: "2026-10-06"). Informe `return_date`
    apenas para ida e volta; deixe em branco para somente ida.

    Ressalva sobre ida e volta: quando `return_date` é informado, a busca é feita
    como round-trip no Google Flights, mas cada itinerário retornado traz apenas
    os trechos de uma das direções (normalmente a ida). Portanto, apresente o
    preço como o valor da busca de ida e volta configurada, sem afirmar
    categoricamente que ele cobre os dois sentidos ou apenas um. O HTML gerado já
    inclui essa observação no cabeçalho.

    Args:
        from_airport: Código IATA de origem (3 letras).
        to_airport: Código IATA de destino (3 letras).
        departure_date: Data de ida, "YYYY-MM-DD".
        return_date: Data de volta, "YYYY-MM-DD". Omita para somente ida.
        seat: "economy", "premium-economy", "business" ou "first".
        adults: Número de adultos.
        children: Número de crianças.
        infants_in_seat: Bebês com assento próprio.
        infants_on_lap: Bebês no colo (não pode exceder o número de adultos).
        max_stops: Máximo de escalas por trecho (0 = somente voos diretos).
        airlines: Lista de códigos IATA de companhias ou alianças para filtrar.
        currency: Moeda dos preços (ex.: "BRL", "USD", "EUR").
        language: Idioma dos resultados (ex.: "pt-BR").
        carry_on_bags: Bagagens de mão a considerar na estimativa de preço.
        checked_bags: Bagagens despachadas a considerar na estimativa de preço.
        max_price: Preço máximo na moeda selecionada.

    Returns:
        Dicionário com `count`, `cheapest_price`, `currency`, `query`
        (parâmetros normalizados), `flights` (lista ordenada por preço) e `html`
        (página completa e pronta para exibição).
    """
    return _do_search_flights(
        from_airport=from_airport,
        to_airport=to_airport,
        departure_date=departure_date,
        return_date=return_date,
        seat=seat,
        adults=adults,
        children=children,
        infants_in_seat=infants_in_seat,
        infants_on_lap=infants_on_lap,
        max_stops=max_stops,
        airlines=airlines,
        currency=currency,
        language=language,
        carry_on_bags=carry_on_bags,
        checked_bags=checked_bags,
        max_price=max_price,
    )


@mcp.tool()
def search_airports(query: str, limit: int = 8) -> list[dict[str, str]]:
    """Procura aeroportos por código IATA, nome ou cidade.

    Use antes de `search_flights` sempre que o usuário informar um nome de cidade
    ou de aeroporto em vez do código IATA de 3 letras.

    A base de dados só tem nomes de lugares em inglês. As cidades mais comuns
    (Lisboa, Londres, Roma, Nova York, Moscou etc.) já têm tradução automática
    embutida. Se a busca em português não retornar nada, tente de novo com o
    nome da cidade em inglês antes de concluir que não existe (ex.: "Munique"
    -> "Munich", "Praga" -> "Prague").

    Args:
        query: Texto livre — código IATA, nome do aeroporto ou nome da cidade.
        limit: Número máximo de resultados.

    Returns:
        Lista de dicionários com `code`, `name`, `city` e `country`.
    """
    return _search_airports(query, limit)


if __name__ == "__main__":
    mcp.run()
