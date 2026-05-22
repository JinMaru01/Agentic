# ============================================================
# Multi-Agent Enterprise POC
# Organisation AI Assistant Workflow
# ============================================================
#
# Features:
# - Multiple AI Agents
# - Agent-to-Agent Communication
# - Tool Calling
# - Shared Workflow
# - Enterprise-style Architecture
#
# Agents:
# 1. Planner Agent
# 2. Search Agent
# 3. Pricing Agent
# 4. Recommendation Agent
#
# Tech:
# - LangChain
# - OpenAI
# - DuckDuckGo Search
#
# Install:
# pip install langchain langchain-openai duckduckgo-search
#
# ============================================================

from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from duckduckgo_search import DDGS

# ============================================================
# LLM (OLLAMA)
# ============================================================

llm = ChatOllama(
    model="qwen3:4b-instruct",
    temperature=0,
    base_url="http://10.123.0.218:8080"
)

# ============================================================
# TOOLS
# ============================================================

@tool
def amazon_search(product: str) -> str:
    """Search Amazon-like results using DuckDuckGo"""
    with DDGS() as ddgs:
        results = ddgs.text(f"Amazon best price for {product}", max_results=3)
        print("amazon result: ", results)
        return "\n\n".join(
            f"{r['title']}\n{r['href']}" for r in results
        )


@tool
def flipkart_search(product: str) -> str:
    """Search Flipkart-like results using DuckDuckGo"""
    with DDGS() as ddgs:
        results = ddgs.text(f"Flipkart deals for {product}", max_results=3)
        print("flipkart_search result: ", results)
        return "\n\n".join(
            f"{r['title']}\n{r['href']}" for r in results
        )

# ============================================================
# AGENTS (LangGraph ReAct agents)
# ============================================================

amazon_agent = create_react_agent(llm, [amazon_search])
flipkart_agent = create_react_agent(llm, [flipkart_search])
planner_agent = create_react_agent(llm, [])
recommendation_agent = create_react_agent(llm, [])

# ============================================================
# INPUT
# ============================================================

user_query = "Find best deal for iPhone 15 Pro 128GB in India"

# ============================================================
# STEP 1: PLANNING
# ============================================================

print("\n--- PLANNER ---")

plan = planner_agent.invoke({
    "messages": [("user", f"""
Create execution plan:

{user_query}

Steps:
1. Amazon search
2. Flipkart search
3. Compare prices
4. Recommend best deal
""")]
})

print(plan)

# ============================================================
# STEP 2: AMAZON
# ============================================================

print("\n--- AMAZON ---")

amazon_result = amazon_agent.invoke({
    "messages": [("user", f"Find deals for {user_query}")]
})

print(amazon_result)

# ============================================================
# STEP 3: FLIPKART
# ============================================================

print("\n--- FLIPKART ---")

flipkart_result = flipkart_agent.invoke({
    "messages": [("user", f"Find deals for {user_query}")]
})

print(flipkart_result)

# ============================================================
# STEP 4: RECOMMENDATION
# ============================================================

print("\n--- FINAL RECOMMENDATION ---")

final_response = recommendation_agent.invoke({
    "messages": [("user", f"""
Compare results:

AMAZON:
{amazon_result}

FLIPKART:
{flipkart_result}

Return:
- best price
- best platform
- final recommendation

response should be table format easy for human to understand
""")]
})

print(final_response)