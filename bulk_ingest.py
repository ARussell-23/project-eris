import os
import csv
import json
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

PROGRESS_FILE = "ingest_progress.json"

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_progress(completed):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(list(completed), f)

def bulk_ingest(clear=True, resume=False):
    """
    Walks each document type folder and ingests all PDFs found.
    clear=True wipes the existing index before starting (default for re-index).
    resume=False starts fresh (default for re-index).
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
        if os.path.exists(PROGRESS_FILE):
            os.remove(PROGRESS_FILE)
        print()

    completed = load_progress()
    if completed and resume:
        print(f"Resuming — {len(completed)} files already ingested, skipping.\n")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    flag_file = f"flagged_metadata_{timestamp}.csv"
    flagged = []

    total_files = 0
    total_chunks = 0
    failed = []
    skipped = 0

    for folder, doc_type in FOLDER_TYPE_MAP.items():
        if not os.path.exists(folder):
            continue

        files = [f for f in os.listdir(folder) if f.endswith(".pdf")]
        if not files:
            continue

        print(f"\n── {doc_type}S ({len(files)} files) ──────────────────────")

        for i, filename in enumerate(files):
            if resume and filename in completed:
                skipped += 1
                continue

            pdf_path = os.path.join(folder, filename)
            print(f"[{i+1}/{len(files)}] {filename}")

            try:
                pages = extract_pdf_text(pdf_path)

                if not pages:
                    print(f"    ✗ No text extracted — skipping")
                    failed.append({"filename": filename, "error": "No text extracted"})
                    continue

                metadata = extract_metadata(pdf_path, doc_type)

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

                if not chunks:
                    print(f"    ✗ No chunks generated — skipping")
                    failed.append({"filename": filename, "error": "No chunks generated"})
                    continue

                stored = store_chunks(chunks)
                total_chunks += stored
                total_files += 1

                completed.add(filename)
                save_progress(completed)

                print(f"    ✓ {metadata['title'] or filename} — {metadata['author'] or 'unknown'}")
                print(f"      {len(pages)} pages · {stored} chunks")

            except Exception as e:
                print(f"    ✗ Failed: {e}")
                failed.append({"filename": filename, "error": str(e)})

    if flagged:
        with open(flag_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["filename", "doc_type", "title", "author", "folder"])
            writer.writeheader()
            writer.writerows(flagged)
        print(f"\n⚑ {len(flagged)} files flagged for metadata review → {flag_file}")

    print(f"\n{'─' * 50}")
    print(f"Ingestion complete.")
    print(f"Files processed this run: {total_files}")
    if skipped:
        print(f"Files skipped (already indexed): {skipped}")
    print(f"Total chunks stored this run: {total_chunks}")

    if failed:
        print(f"\nFailed files ({len(failed)}):")
        for f in failed:
            print(f"  - {f['filename']}: {f['error']}")

    if not failed and os.path.exists(PROGRESS_FILE):
        os.remove(PROGRESS_FILE)
        print("\nProgress file cleared — full ingestion complete.")

if __name__ == "__main__":
    bulk_ingest(clear=True, resume=False)
