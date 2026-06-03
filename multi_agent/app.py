from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path

from .services.langgraph_service import AgentService

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI()

# Serve static files
app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR / "static"),
    name="static"
)

agent_service = AgentService()


class ChatRequest(BaseModel):
    message: str


# =========================
# UI ENTRY (NO JINJA)
# =========================
@app.get("/")
def home():
    return FileResponse(BASE_DIR / "templates" / "index.html")


# =========================
# CHAT API
# =========================
@app.post("/chat")
def chat(req: ChatRequest):

    state = agent_service.chat(req.message)

    print(state)

    return {
        "answer": state["answer"],
        "agent": state["agent"]
    }