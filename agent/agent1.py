from langchain_community.chat_models import ChatOllama

llm = ChatOllama(
    model="llama3.1:8b",
    temperature=0,
    base_url="http://10.123.0.218:8080"
)

response = llm.invoke("What is an AI agent in simple terms?")
print(response.content)