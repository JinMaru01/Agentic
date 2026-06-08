"""
Entry point for the Multi-Agent POC API server.

Run via uvicorn (supports --reload):
    uvicorn api_server:app --reload --port 8001

Or run directly:
    python api_server.py

API docs available at: http://localhost:8001/docs
"""

from multi_agent.api.main import app

__all__ = ["app"]

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8001,
        log_level="info",
        reload=True,
    )
