from langchain_community.chat_models import ChatOllama
from langchain.tools import tool
from langgraph.graph import StateGraph, START, END
from langchain.messages import (
    HumanMessage,
    SystemMessage,
    ToolMessage,
    AnyMessage
)

from typing_extensions import TypedDict, Annotated
from typing import Literal
import operator

# =========================
# LLM
# =========================

model = ChatOllama(
    model="deepseek-r1:7b",
    base_url="http://10.123.0.218:8080",
    temperature=0
)

# =========================
# Tools
# =========================

@tool
def add(a: int, b: int) -> int:
    return a + b

@tool
def multiply(a: int, b: int) -> int:
    return a * b

@tool
def divide(a: int, b: int) -> float:
    return a / b

tools = [add, multiply, divide]
tools_by_name = {t.name: t for t in tools}

model_with_tools = model.bind_tools(tools)

# =========================
# State
# =========================

class MessagesState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    llm_calls: int

# =========================
# LLM Node
# =========================

def llm_call(state: MessagesState):

    response = model_with_tools.invoke(
        [
            SystemMessage(
                content="You are a math assistant."
            )
        ] + state["messages"]
    )

    return {
        "messages": [response],
        "llm_calls": state.get("llm_calls", 0) + 1
    }

# =========================
# Tool Node
# =========================

def tool_node(state: MessagesState):

    results = []

    for tool_call in state["messages"][-1].tool_calls:

        tool = tools_by_name[tool_call["name"]]

        observation = tool.invoke(tool_call["args"])

        results.append(
            ToolMessage(
                content=str(observation),
                tool_call_id=tool_call["id"]
            )
        )

    return {"messages": results}

# =========================
# Routing Logic
# =========================

def should_continue(
    state: MessagesState
) -> Literal["tool_node", END]:

    last_message = state["messages"][-1]

    if last_message.tool_calls:
        return "tool_node"

    return END

# =========================
# Build Graph
# =========================

builder = StateGraph(MessagesState)

builder.add_node("llm_call", llm_call)
builder.add_node("tool_node", tool_node)

builder.add_edge(START, "llm_call")

builder.add_conditional_edges(
    "llm_call",
    should_continue
)

builder.add_edge("tool_node", "llm_call")

agent = builder.compile()

# =========================
# Run
# =========================

response = agent.invoke({
    "messages": [
        HumanMessage(
            content="What is (5 + 3) * 10?"
        )
    ]
})

for msg in response["messages"]:
    print(msg)