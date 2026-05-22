from agents.lead_agent import lead_agent


def run_access_workflow(user_request: str):

    response = lead_agent.run(user_request)

    return response