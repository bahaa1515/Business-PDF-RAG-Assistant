"""Project configuration constants."""

MODEL_NAME = "gpt-4o-mini"
EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_CHUNK_SIZE = 800
DEFAULT_CHUNK_OVERLAP = 150
TOP_K = 4
DEFAULT_RETRIEVAL_METHOD = "similarity"
RETRIEVAL_METHOD_OPTIONS = ["similarity", "mmr"]
CHROMA_PERSIST_DIRECTORY = "./data/chroma"
