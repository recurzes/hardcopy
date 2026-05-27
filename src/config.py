from dotenv import load_dotenv
import os

load_dotenv()

TODOIST_API_KEY = os.getenv("TODOIST_API_KEY")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
VENDOR_ID = 0x483
PRODUCT_ID = 0x070B
MAX_WIDTH = 32
