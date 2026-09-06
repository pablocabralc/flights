"""ASGI entrypoint for serving the MCP server over Streamable HTTP (e.g. on Vercel).

Stateless + JSON response mode is used because serverless functions don't keep
a persistent process around to hold SSE streams or session state between
requests.
"""

from mcp.server.transport_security import TransportSecuritySettings

from .server import mcp

app = mcp.streamable_http_app(
    stateless_http=True,
    json_response=True,
    # Deployed behind Vercel's rotating preview/alias hostnames with no
    # session/auth state to protect, so the DNS-rebinding Host check (meant
    # for locally-bound servers) would just reject legitimate traffic.
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)
