import os
from dotenv import load_dotenv

load_dotenv()

LLM_URL = os.getenv("LLM_URL")
LLM_SERVER = os.getenv("LLM_SERVER")

MODEL_CONFIG = {
    "default": os.getenv("MODEL_DEFAULT"),
    "fast": os.getenv("MODEL_FAST"),
    "strong": os.getenv("MODEL_STRONG"),
    "light": os.getenv("MODEL_LIGHT"),
}