from smolagents import CodeAgent

from models import build_model
from config import MODEL_SYSTEM

from tools.jira_tool import provision_jira_access


system_access_agent = CodeAgent(
    name="system_access_agent",
    description="""
    Responsible for:
    - provisioning access
    - system execution
    - applying permissions
    - validating access
    """,
    tools=[
        provision_jira_access
    ],
    model=build_model(MODEL_SYSTEM)
)