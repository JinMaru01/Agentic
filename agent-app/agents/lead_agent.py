from smolagents import CodeAgent

from models import build_model
from config import MODEL_SUPERVISOR

from agents.document_agent import document_agent
from agents.system_access_agent import system_access_agent
from agents.audit_agent import audit_agent


lead_agent = CodeAgent(
    name="lead_agent",
    description="""
    Responsible for:
    - validating user requests
    - authorization checks
    - routing tasks
    - monitoring workflow
    - final verification
    """,
    tools=[],
    managed_agents=[
        document_agent,
        system_access_agent,
        audit_agent
    ],
    model=build_model(MODEL_SUPERVISOR)
)