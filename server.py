from mcp.server.sse import SseServerTransport
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import HTMLResponse
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
import requests
from bs4 import BeautifulSoup
import logging
import traceback
import sys
import os
import uvicorn

# Setup logging for Render logs
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("web-extractor")

# MCP server definition
app = FastMCP("web-content-extractor")

@app.tool()
def extract_web_content(url: str) -> str:
    """Extract visible text from a web page."""
    try:
        logger.info(f"Extracting content from: {url}")
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
        logger.error(f"Error extracting content: {str(e)}")
        logger.error(traceback.format_exc())
        return f"Error: {str(e)}"

# Setup SSE transport
sse = SseServerTransport("/messages")

async def handle_sse(scope, receive, send):
    try:
        logger.info("SSE connection requested")
        async with sse.connect_sse(scope, receive, send) as streams:
            logger.info("SSE connection established")
            await app.run(streams[0], streams[1], app.create_initialization_options())
    except Exception as e:
        logger.error(f"SSE connection error: {str(e)}")
        logger.error(traceback.format_exc())
        await send({
            'type': 'http.response.start',
            'status': 500,
            'headers': [[b'content-type', b'application/json']],
        })
        await send({
            'type': 'http.response.body',
            'body': f'{{"error": "{str(e)}"}}'.encode('utf-8'),
        })

async def handle_messages(scope, receive, send):
    try:
        logger.info("Message received")
        await sse.handle_post_message(scope, receive, send)
    except Exception as e:
        logger.error(f"Message handling error: {str(e)}")
        logger.error(traceback.format_exc())
        await send({
            'type': 'http.response.start',
            'status': 500,
            'headers': [[b'content-type', b'application/json']],
        })
        await send({
            'type': 'http.response.body',
            'body': f'{{"error": "{str(e)}"}}'.encode('utf-8'),
        })

async def homepage(request):
    return HTMLResponse("""
    <html>
        <head><title>Web Content Extractor MCP Server</title></head>
        <body>
            <h1>Web Content Extractor MCP Server</h1>
            <p>This is an MCP server that extracts visible text from web pages.</p>
        </body>
    </html>
    """)

# Starlette app definition
starlette_app = Starlette(
    routes=[
        Route("/", endpoint=homepage),
        Route("/sse", endpoint=lambda scope, receive, send: handle_sse(scope, receive, send)),
        Route("/messages", endpoint=handle_messages, methods=["POST"]),
    ],
    middleware=[
        Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    ],
    debug=True,
)

# Run the app with Uvicorn
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"Starting MCP SSE server on port {port}")
    uvicorn.run(starlette_app, host="0.0.0.0", port=port, log_level="info")
