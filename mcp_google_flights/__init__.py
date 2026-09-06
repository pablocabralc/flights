"""Servidor MCP que expõe o scraper do Google Flights (`fast_flights`)."""

__all__ = ["mcp"]


def __getattr__(name: str):
    if name == "mcp":
        from .server import mcp

        return mcp
    raise AttributeError(name)
