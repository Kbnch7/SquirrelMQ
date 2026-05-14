from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
VISIBILITY_TIMEOUT_SECONDS = int(os.getenv("VISIBILITY_TIMEOUT_SECONDS", "30"))
MAX_DELIVERY_ATTEMPTS = int(os.getenv("MAX_DELIVERY_ATTEMPTS", "5"))
METRICS_HOST = os.getenv("METRICS_HOST", "0.0.0.0")
METRICS_PORT = int(os.getenv("METRICS_PORT", "8000"))
