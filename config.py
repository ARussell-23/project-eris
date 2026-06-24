import os

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
DOCUMENTS_DIR   = os.path.join(BASE_DIR, "documents")
BOOKS_DIR       = os.path.join(BASE_DIR, "documents", "books")
ARTICLES_DIR    = os.path.join(BASE_DIR, "documents", "articles")
DOCS_DIR        = os.path.join(BASE_DIR, "documents", "documents")
CHROMA_DIR      = os.path.join(BASE_DIR, "data", "chroma")
COLLECTION_NAME = "eris_documents"

# ── Chunking ───────────────────────────────────────────────────────────────
CHUNK_SIZE      = 400   # target characters per chunk (sentence-aware, splits at boundaries
CHUNK_OVERLAP   = 50    # characters of overlap between chunks

# ── Embedding model ────────────────────────────────────────────────────────
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# ── Ollama ─────────────────────────────────────────────────────────────────
OLLAMA_MODEL    = "mistral:7b-instruct"
OLLAMA_BASE_URL = "http://localhost:11434"

# ── Retrieval ──────────────────────────────────────────────────────────────
MAX_RESULTS     = 5     # maximum sources returned per query
NULL_THRESHOLD  = 0.3   # minimum similarity score — below this, no result returned

# ── Supported file types ───────────────────────────────────────────────────
ALLOWED_EXTENSIONS = [".pdf", ".docx", ".pptx"]

# ── Upload ─────────────────────────────────────────────────────────────────
UPLOAD_DIR      = os.path.join(BASE_DIR, "uploads")
