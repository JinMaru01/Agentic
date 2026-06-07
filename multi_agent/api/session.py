import uuid
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage


class Session:
    def __init__(self, session_id: str):
        self.session_id  = session_id
        self.created_at  = datetime.now().isoformat()
        self.last_active = datetime.now().isoformat()
        self.histories: Dict[str, list] = defaultdict(list)
        self.last_agent  = "none"
        self.messages: List[dict] = []

    def get_history(self, agent_key: str) -> list:
        return self.histories[agent_key]

    def update_history(self, agent_key: str, query: str, result: dict) -> None:
        self.histories[agent_key].append(HumanMessage(content=query))
        for msg in result.get("messages", []):
            if isinstance(msg, (AIMessage, ToolMessage)):
                self.histories[agent_key].append(msg)
        self.last_agent  = agent_key
        self.last_active = datetime.now().isoformat()

    def add_display_message(self, role: str, content: str, agent_used: Optional[str] = None) -> None:
        self.messages.append({
            "role":       role,
            "content":    content,
            "agent_used": agent_used,
            "timestamp":  datetime.now().isoformat(),
        })
        self.last_active = datetime.now().isoformat()


class SessionStore:
    def __init__(self):
        self._sessions: Dict[str, Session] = {}

    def create(self) -> Session:
        session_id = str(uuid.uuid4())
        session    = Session(session_id)
        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> Optional[Session]:
        return self._sessions.get(session_id)

    def delete(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def list_all(self) -> List[dict]:
        return [
            {
                "session_id":    s.session_id,
                "created_at":    s.created_at,
                "last_active":   s.last_active,
                "message_count": len(s.messages),
            }
            for s in self._sessions.values()
        ]


# Singleton used across the application
session_store = SessionStore()
