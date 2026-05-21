from langchain_community.chat_models import ChatOllama
from langchain.agents import create_react_agent, AgentExecutor
from langchain_core.tools import tool
from langchain import hub

llm = ChatOllama(model="llama3.1")

@tool
def add(a: int, b: int) -> int:
    return a + b

tools = [add]

prompt = hub.pull("hwchase17/react")

agent = create_react_agent(llm, tools, prompt)

executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

result = executor.invoke({"input": "Add 10 and 25"})
print(result)