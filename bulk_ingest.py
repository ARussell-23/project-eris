import os
import csv
from datetime import datetime
from ingest.pdf_extract import extract_pdf_text
from ingest.metadata import extract_metadata
from ingest.chunker import chunk_pages
from ingest.store import store_chunks
from config import BOOKS_DIR, ARTICLES_DIR, DOCS_DIR

# Maps folder path to document type label
FOLDER_TYPE_MAP = {
    BOOKS_DIR:    "BOOK",
    ARTICLES_DIR: "ARTICLE",
    DOCS_DIR:     "DOCUMENT"
}

def bulk_ingest(clear=False):
    """
    Walks each document type folder and ingests all PDFs found.
    Logs files with missing/incomplete metadata to a review file.
    Optionally clears the index before starting.
    """
    if clear:
        from ingest.store import get_collection
        import chromadb
        from config import CHROMA_DIR, COLLECTION_NAME
        client = chromadb.PersistentClient(path=CHROMA_DIR)
        try:
            client.delete_collection(COLLECTION_NAME)
            print("Existing index cleared.")
        except Exception:
            print("No existing index found — starting fresh.")
        client.get_or_create_collection(COLLECTION_NAME)
        print()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    flag_file = f"flagged_metadata_{timestamp}.csv"
    flagged = []

    total_files = 0
    total_chunks = 0
    failed = []

    for folder, doc_type in FOLDER_TYPE_MAP.items():
        if not os.path.exists(folder):
            continue

        files = [f for f in os.listdir(folder) if f.endswith(".pdf")]
        if not files:
            continue

        print(f"\n── {doc_type}S ({len(files)} files) ──────────────────────")

        for i, filename in enumerate(files):
            pdf_path = os.path.join(folder, filename)
            print(f"[{i+1}/{len(files)}] {filename}")

            try:
                pages = extract_pdf_text(pdf_path)
                metadata = extract_metadata(pdf_path, doc_type)

                # Flag incomplete metadata for later review
                if not metadata["title"] or not metadata["author"]:
                    flagged.append({
                        "filename": filename,
                        "doc_type": doc_type,
                        "title": metadata["title"],
                        "author": metadata["author"],
                        "folder": folder
                    })
                    print(f"    ⚑ Incomplete metadata flagged for review")

                chunks = chunk_pages(
                    pages,
                    title=metadata["title"],
                    author=metadata["author"],
                    doc_type=metadata["doc_type"],
                    source_file=metadata["source_file"]
                )
                stored = store_chunks(chunks)
                total_chunks += stored
                total_files += 1
                print(f"    ✓ {metadata['title'] or filename} — {metadata['author'] or 'unknown'}")
                print(f"      {len(pages)} pages · {stored} chunks")

            except Exception as e:
                print(f"    ✗ Failed: {e}")
                failed.append({"filename": filename, "error": str(e)})

    # Write flagged metadata to CSV for review
    if flagged:
        with open(flag_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["filename", "doc_type", "title", "author", "folder"])
            writer.writeheader()
            writer.writerows(flagged)
        print(f"\n⚑ {len(flagged)} files flagged for metadata review → {flag_file}")

    print(f"\n{'─' * 50}")
    print(f"Ingestion complete.")
    print(f"Files processed: {total_files}")
    print(f"Total chunks stored: {total_chunks}")

    if failed:
        print(f"\nFailed files ({len(failed)}):")
        for f in failed:
            print(f"  - {f['filename']}: {f['error']}")

if __name__ == "__main__":
    bulk_ingest(clear=True)
