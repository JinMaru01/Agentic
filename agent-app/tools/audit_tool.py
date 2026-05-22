from smolagents import tool
from datetime import datetime


@tool
def log_audit_event(event: str) -> str:
    """
    Store audit execution event.
    """

    with open("logs/audit.log", "a") as f:
        f.write(f"{datetime.utcnow()} | {event}\n")

    return "Audit event logged"