"""ASGI entrypoint for serving the MCP server over Streamable HTTP (e.g. on Vercel).

Stateless + JSON response mode is used because serverless functions don't keep
a persistent process around to hold SSE streams or session state between
requests.
"""

from .server import mcp

app = mcp.streamable_http_app(stateless_http=True, json_response=True)
