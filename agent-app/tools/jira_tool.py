from smolagents import tool
import requests


@tool
def provision_jira_access(username: str, role: str) -> str:
    """
    Provision Jira access for a user.
    """

    payload = {
        "username": username,
        "role": role
    }

    # Replace with actual internal API
    response = requests.post(
        "http://internal-api/jira/access",
        json=payload
    )

    return response.text