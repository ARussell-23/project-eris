import sqlite3
import chromadb
from sentence_transformers import SentenceTransformer
from config import CHROMA_DIR, EMBEDDING_MODEL, COLLECTION_NAME

SQLITE_PATH = "data/search_index.db"

client = chromadb.PersistentClient(path=CHROMA_DIR)
model = SentenceTransformer(EMBEDDING_MODEL)

def get_collection():
    """
    Returns the ChromaDB collection, creating it if it doesn't exist yet.
    """
    return client.get_or_create_collection(name=COLLECTION_NAME)

def _write_to_sqlite(chunks, ids):
    """
    Writes chunks to SQLite full-text search index.
    Creates the database if it doesn't exist yet.
    """
    try:
        conn = sqlite3.connect(SQLITE_PATH)
        c = conn.cursor()

        # Create tables if they don't exist
        c.executescript("""
            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY,
                source_file TEXT,
                title TEXT,
                author TEXT,
                doc_type TEXT,
                page_number INTEGER,
                text TEXT
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                text,
                source_file UNINDEXED,
                title UNINDEXED,
                author UNINDEXED,
                doc_type UNINDEXED,
                page_number UNINDEXED,
                content='chunks',
                content_rowid='rowid'
            );
        """)

        rows = [
            (
                ids[i],
                chunks[i]["source_file"],
                chunks[i]["title"],
                chunks[i]["author"],
                chunks[i]["doc_type"],
                chunks[i]["page_number"],
                chunks[i]["text"]
            )
            for i in range(len(chunks))
        ]

        c.executemany("""
            INSERT OR REPLACE INTO chunks
            (id, source_file, title, author, doc_type, page_number, text)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, rows)

        c.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')")
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Warning: SQLite write failed: {e}")

def store_chunks(chunks):
    """
    Embeds a list of chunk dictionaries and stores them in ChromaDB and SQLite.
    Uses batching to stay within ChromaDB's max batch size limit.
    """
    collection = get_collection()

    texts = [chunk["text"] for chunk in chunks]
    embeddings = model.encode(texts, show_progress_bar=True).tolist()

    ids = [
        f"{chunk['source_file']}::p{chunk['page_number']}::{i}"
        for i, chunk in enumerate(chunks)
    ]

    metadatas = [
        {
            "title": chunk["title"],
            "author": chunk["author"],
            "doc_type": chunk["doc_type"],
            "source_file": chunk["source_file"],
            "page_number": chunk["page_number"]
        }
        for chunk in chunks
    ]

    batch_size = 5000
    for i in range(0, len(chunks), batch_size):
        collection.add(
            documents=texts[i:i+batch_size],
            embeddings=embeddings[i:i+batch_size],
            metadatas=metadatas[i:i+batch_size],
            ids=ids[i:i+batch_size]
        )

    # Write to SQLite for keyword search
    _write_to_sqlite(chunks, ids)

    return len(chunks)
