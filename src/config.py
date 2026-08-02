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

# Quiz daemon
QUIZ_INTERVAL = int(os.getenv("QUIZ_INTERVAL", "120"))      # minutes between quizzes
QUIZ_ANSWER_DELAY = int(os.getenv("QUIZ_ANSWER_DELAY", "5")) # minutes before answer prints
QUIZ_TOPIC = os.getenv("QUIZ_TOPIC", "my study notes")       # shown in LLM system prompt
QUIZ_POOL_MIN = int(os.getenv("QUIZ_POOL_MIN", "50"))        # min questions to generate on ingest
