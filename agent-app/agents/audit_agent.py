from smolagents import CodeAgent

from models import build_model
from config import MODEL_AUDIT

from tools.audit_tool import log_audit_event


audit_agent = CodeAgent(
    name="audit_agent",
    description="""
    Responsible for:
    - audit logs
    - compliance traceability
    - execution tracking
    """,
    tools=[
        log_audit_event
    ],
    model=build_model(MODEL_AUDIT)
)