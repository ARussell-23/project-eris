"""
build_search_index.py
One-time script to build a SQLite full-text search index from ChromaDB data.
Run this once after bulk ingestion. Future ingests update SQLite automatically via store.py.
"""
import sqlite3
import chromadb
from config import CHROMA_DIR, COLLECTION_NAME

SQLITE_PATH = "data/search_index.db"

def build_index():
    print("Connecting to ChromaDB...")
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    collection = client.get_collection(COLLECTION_NAME)
    total = collection.count()
    print(f"Total chunks in ChromaDB: {total}")

    print("Building SQLite index...")
    conn = sqlite3.connect(SQLITE_PATH)
    c = conn.cursor()

    # Create FTS5 virtual table for full-text search
    c.executescript("""
        DROP TABLE IF EXISTS chunks;
        DROP TABLE IF EXISTS chunks_fts;

        CREATE TABLE chunks (
            id TEXT PRIMARY KEY,
            source_file TEXT,
            title TEXT,
            author TEXT,
            doc_type TEXT,
            page_number INTEGER,
            text TEXT
        );

        CREATE VIRTUAL TABLE chunks_fts USING fts5(
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

    # Fetch all chunks from ChromaDB in batches
    batch_size = 5000
    offset = 0
    inserted = 0

    while offset < total:
        print(f"  Processing chunks {offset}–{min(offset+batch_size, total)}...")
        results = collection.get(
            limit=batch_size,
            offset=offset,
            include=["documents", "metadatas"]
        )

        rows = []
        for i, doc_id in enumerate(results["ids"]):
            meta = results["metadatas"][i]
            text = results["documents"][i]
            rows.append((
                doc_id,
                meta.get("source_file", ""),
                meta.get("title", ""),
                meta.get("author", ""),
                meta.get("doc_type", ""),
                meta.get("page_number", 0),
                text
            ))

        c.executemany("""
            INSERT OR REPLACE INTO chunks
            (id, source_file, title, author, doc_type, page_number, text)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, rows)

        # Update FTS index
        c.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')")

        conn.commit()
        inserted += len(rows)
        offset += batch_size

    conn.close()
    print(f"\nDone. {inserted} chunks indexed in SQLite.")
    print(f"Index saved to: {SQLITE_PATH}")

if __name__ == "__main__":
    build_index()
