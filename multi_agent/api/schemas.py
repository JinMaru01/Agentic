from pydantic import BaseModel
from typing import Optional, List


class ChatRequest(BaseModel):
    session_id: str
    message: str
    selected_agent: str = "auto"  # "auto" | "calculator" | "mall"


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str
    agent_used: Optional[str] = None
    timestamp: str


class ChatResponse(BaseModel):
    session_id: str
    response: str
    agent_used: str
    suggested_agent: Optional[str] = None
    suggestion_reason: Optional[str] = None
    error: Optional[str] = None


class AgentInfo(BaseModel):
    id: str
    name: str
    description: str
    capabilities: List[str]
    icon: str
    color: str


class SessionInfo(BaseModel):
    session_id: str
    created_at: str
    last_active: str
    message_count: int


class CreateSessionResponse(BaseModel):
    session_id: str


class HistoryResponse(BaseModel):
    session_id: str
    messages: List[ChatMessage]
