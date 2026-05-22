from smolagents import tool


@tool
def retrieve_access_template(system_name: str) -> str:
    """
    Retrieve onboarding template for internal systems.
    """

    templates = {
        "jira": "Jira developer access template",
        "vpn": "VPN onboarding template",
        "gitlab": "GitLab engineer onboarding"
    }

    return templates.get(system_name.lower(), "No template found")