from mcp.server.sse import SseServerTransport
from mcp.server import Server
from starlette.applications import Starlette
from starlette.routing import Route
import requests
from bs4 import BeautifulSoup

# Create MCP server instance
app = Server("web-content-extractor")

@app.tool()
def extract_web_content(url: str) -> str:
    """Extract visible text content from a web page."""
    try:
        if not url.startswith("http://") and not url.startswith("https://"):
            return "Invalid URL. It must start with http:// or https://"

        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')

        # Remove scripts and styles
        for tag in soup(['script', 'style']):
            tag.decompose()

        # Extract visible text
        raw_text = soup.get_text()
        cleaned = "\n".join(
            line.strip() for line in raw_text.splitlines() if line.strip()
        )

        return cleaned
    except Exception as e:
        return f"Error: {str(e)}"

# Setup SSE transport
sse = SseServerTransport("/messages")

async def handle_sse(scope, receive, send):
    async with sse.connect_sse(scope, receive, send) as streams:
        await app.run(streams[0], streams[1], app.create_initialization_options())

async def handle_messages(scope, receive, send):
    await sse.handle_post_message(scope, receive, send)

# Starlette app for HTTP routes
starlette_app = Starlette(routes=[
    Route("/sse", endpoint=handle_sse),
    Route("/messages", endpoint=handle_messages, methods=["POST"]),
])
