from smolagents import LiteLLMModel
from config import *


def build_model(model_id: str):
    return LiteLLMModel(
        provider="ollama_chat",
        model_id=model_id,
        api_base=OLLAMA_BASE_URL,
        temperature=0
    )