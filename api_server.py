"""
Entry point for the Multi-Agent POC API server.

Run from the RAG project root:
    python api_server.py

API docs available at: http://localhost:8001/docs
"""

import uvicorn

if __name__ == "__main__":
    from multi_agent.api.main import app

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        log_level="info",
    )
