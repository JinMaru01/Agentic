from dataclasses import dataclass
from load_env import MODEL_CONFIG, LLM_SERVER

@dataclass
class AgentConfig:
    model_name: str = MODEL_CONFIG['strong']
    base_url: str = LLM_SERVER
    temperature: float = 0