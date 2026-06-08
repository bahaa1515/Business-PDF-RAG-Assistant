"""Project configuration constants."""

MODEL_NAME = "gpt-4o-mini"
EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_CHUNK_SIZE = 800
DEFAULT_CHUNK_OVERLAP = 150
TOP_K = 4
DEFAULT_RETRIEVAL_METHOD = "similarity"
RETRIEVAL_METHOD_OPTIONS = ["similarity", "mmr"]
CHROMA_PERSIST_DIRECTORY = "./data/chroma"
# Optional threshold for retrieval score filtering (None to disable)
RETRIEVAL_SCORE_THRESHOLD = None

# Refusal message used when information is not found in documents
REFUSAL_MESSAGE = "I could not find this information in the uploaded documents."

# Paths for evaluation and persisted data
DATA_DIR = "./data"
CHAT_DB_PATH = f"{DATA_DIR}/chat_history.db"
EVAL_DIR = "./eval"
EVAL_DEFAULT_CSV = f"{EVAL_DIR}/evaluation_questions.csv"
EVAL_RESULTS_DIR = f"{EVAL_DIR}/results"
