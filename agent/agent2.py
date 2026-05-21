from langchain_community.chat_models import ChatOllama
from langchain.agents import initialize_agent, Tool, AgentType

llm = ChatOllama(
    model="llama3.1:8b",
    base_url="http://10.123.0.218:8080",
    temperature=0
)

def calculator(x: str):
    return str(eval(x))

tools = [
    Tool(
        name="Calculator",
        func=calculator,
        description="Useful for math"
    )
]

agent = initialize_agent(
    tools,
    llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True
)

print(agent.invoke({"input": "What is 100 * 23 + 7?"}))