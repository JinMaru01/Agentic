from smolagents import CodeAgent, DuckDuckGoSearchTool, LiteLLMModel

# point LiteLLMModel at Ollama model id
model = LiteLLMModel(
    provider="ollama_chat",
    model_id="ollama/qwen3:4b-instruct",
    api_base="http://10.123.0.218:8080"
)

tools = [DuckDuckGoSearchTool()]
agent = CodeAgent(tools=tools, model=model)

print(agent.run("What day is it today?"))
