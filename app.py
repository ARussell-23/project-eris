import os
import sqlite3
from flask import Flask, render_template, request, jsonify, session, send_file, abort
from guide.response import ask_guide
from ingest.convert import prepare_file
from ingest.metadata import extract_metadata
from ingest.pdf_extract import extract_pdf_text
from ingest.chunker import chunk_pages
from ingest.store import store_chunks, get_collection
from config import UPLOAD_DIR, ALLOWED_EXTENSIONS, BOOKS_DIR, ARTICLES_DIR, DOCS_DIR, CHROMA_DIR, COLLECTION_NAME

app = Flask(__name__)
app.secret_key = "eris-local-secret"

os.makedirs(UPLOAD_DIR, exist_ok=True)

FOLDER_TYPE_MAP = {
    BOOKS_DIR: "BOOK",
    ARTICLES_DIR: "ARTICLE",
    DOCS_DIR: "DOCUMENT"
}

SQLITE_PATH = "data/search_index.db"

# Cache for document list
_doc_cache = None
_chunk_count_cache = None

def get_all_documents():
    """
    Builds document list from filesystem using SQLite for metadata.
    Fast — one query per folder, not per file.
    Results are cached after first call.
    """
    global _doc_cache, _chunk_count_cache

    if _doc_cache is not None:
        return _doc_cache, _chunk_count_cache

    # Get chunk count from SQLite
    try:
        conn = sqlite3.connect(SQLITE_PATH)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM chunks")
        chunk_count = c.fetchone()[0]

        # Get one metadata row per source file
        c.execute("""
            SELECT source_file, title, author, doc_type
            FROM chunks
            GROUP BY source_file
        """)
        meta_lookup = {row[0]: {"title": row[1], "author": row[2], "doc_type": row[3]}
                      for row in c.fetchall()}
        conn.close()
    except Exception as e:
        print(f"Warning: SQLite lookup failed: {e}")
        chunk_count = 0
        meta_lookup = {}

    docs = []
    for folder, doc_type in FOLDER_TYPE_MAP.items():
        if not os.path.exists(folder):
            continue
        for filename in sorted(os.listdir(folder)):
            if not filename.endswith(".pdf"):
                continue
            pdf_path = os.path.join(folder, filename)
            meta = meta_lookup.get(filename, {})
            # Fall back to filename parsing if not in SQLite
            if not meta.get("title"):
                name = os.path.splitext(filename)[0]
                title = name.replace("_", " ").replace("-", " ").title()
            else:
                title = meta["title"]
            docs.append({
                "filename": filename,
                "filepath": pdf_path,
                "doc_type": meta.get("doc_type", doc_type),
                "title": title,
                "author": meta.get("author", ""),
                "pages": None
            })

    _doc_cache = docs
    _chunk_count_cache = chunk_count
    return docs, chunk_count

def get_doc_metadata(filename):
    """Gets metadata for a single document from SQLite."""
    try:
        conn = sqlite3.connect(SQLITE_PATH)
        c = conn.cursor()
        c.execute("""
            SELECT title, author, doc_type FROM chunks
            WHERE source_file = ? LIMIT 1
        """, (filename,))
        row = c.fetchone()
        conn.close()
        if row:
            return {"title": row[0], "author": row[1], "doc_type": row[2]}
    except Exception:
        pass
    return {}

# ── Routes ──────────────────────────────────────────────────────────────────

@app.route("/")
def landing():
    return render_template("landing.html")

@app.route("/guide")
def guide():
    return render_template("index.html")

@app.route("/search", methods=["POST"])
def search():
    data = request.get_json()
    query = data.get("query", "").strip()

    if not query:
        return jsonify({
            "response": "Nothing to search on. What are you looking for?",
            "results": []
        })

    try:
        output = ask_guide(query)
        return jsonify({
            "response": output["response"],
            "results": output["results"]
        })
    except Exception as e:
        print(f"ERROR in ask_guide: {e}")
        return jsonify({
            "response": f"Internal error: {str(e)}",
            "results": []
        })

@app.route("/archive")
def archive():
    return render_template("archive.html")

@app.route("/archive/documents")
def archive_documents():
    docs, chunk_count = get_all_documents()
    return jsonify({
        "documents": docs,
        "total": len(docs),
        "chunks": chunk_count
    })

@app.route("/archive/doc/<path:filename>")
def archive_doc(filename):
    return render_template("doc.html")

@app.route("/archive/doc-metadata/<path:filename>")
def archive_doc_metadata(filename):
    """Returns metadata for a single document."""
    docs, _ = get_all_documents()
    match = next((d for d in docs if d["filename"] == filename), None)
    if not match:
        # Try SQLite directly
        meta = get_doc_metadata(filename)
        if meta:
            return jsonify({"found": True, "filename": filename, **meta})
        abort(404)
    return jsonify({"found": True, **match})

@app.route("/archive/view/<path:filename>")
def archive_view(filename):
    docs, _ = get_all_documents()
    match = next((d for d in docs if d["filename"] == filename), None)
    if not match:
        abort(404)
    return send_file(match["filepath"], mimetype="application/pdf")

@app.route("/archive/download/<path:filename>")
def archive_download(filename):
    docs, _ = get_all_documents()
    match = next((d for d in docs if d["filename"] == filename), None)
    if not match:
        abort(404)
    return send_file(match["filepath"], mimetype="application/pdf", as_attachment=True, download_name=filename)

@app.route("/archive/search", methods=["GET"])
def archive_search():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"results": [], "total": 0})

    try:
        conn = sqlite3.connect(SQLITE_PATH)
        c = conn.cursor()
        c.execute("""
            SELECT
                chunks.source_file,
                chunks.title,
                chunks.author,
                chunks.doc_type,
                chunks.page_number,
                snippet(chunks_fts, 0, '<mark>', '</mark>', '...', 20) as snippet
            FROM chunks_fts
            JOIN chunks ON chunks.rowid = chunks_fts.rowid
            WHERE chunks_fts MATCH ?
            ORDER BY rank
            LIMIT 50
        """, (query,))
        rows = c.fetchall()
        conn.close()

        results = [
            {
                "source_file": r[0],
                "title": r[1],
                "author": r[2],
                "doc_type": r[3],
                "page_number": r[4],
                "snippet": r[5]
            }
            for r in rows
        ]
        return jsonify({"results": results, "total": len(results)})

    except Exception as e:
        return jsonify({"results": [], "total": 0, "error": str(e)})

@app.route("/archive/update-metadata", methods=["POST"])
def archive_update_metadata():
    global _doc_cache
    data = request.get_json()
    filename = data.get("filename", "").strip()
    title = data.get("title", "").strip()
    author = data.get("author", "").strip()

    if not filename:
        return jsonify({"success": False, "error": "No filename provided"})

    try:
        import chromadb
        client = chromadb.PersistentClient(path=CHROMA_DIR)
        collection = client.get_collection(COLLECTION_NAME)

        results = collection.get(
            where={"source_file": filename},
            include=["metadatas"]
        )

        if not results["ids"]:
            return jsonify({"success": False, "error": "No chunks found for this file"})

        updated_metadatas = []
        for meta in results["metadatas"]:
            updated = dict(meta)
            updated["title"] = title
            updated["author"] = author
            updated_metadatas.append(updated)

        batch_size = 5000
        ids = results["ids"]
        for i in range(0, len(ids), batch_size):
            collection.update(
                ids=ids[i:i+batch_size],
                metadatas=updated_metadatas[i:i+batch_size]
            )

        # Update SQLite
        conn = sqlite3.connect(SQLITE_PATH)
        c = conn.cursor()
        c.execute("UPDATE chunks SET title = ?, author = ? WHERE source_file = ?",
                  (title, author, filename))
        c.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')")
        conn.commit()
        conn.close()

        _doc_cache = None
        return jsonify({"success": True, "chunks_updated": len(ids)})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/ingest")
def ingest():
    return render_template("ingest.html")

@app.route("/ingest/upload", methods=["POST"])
def ingest_upload():
    doc_type = request.form.get("doc_type", "ARTICLE").upper()
    files = request.files.getlist("files")

    if not files:
        return jsonify({"error": "No files received."}), 400

    pending = []

    for file in files:
        filename = file.filename
        ext = os.path.splitext(filename)[1].lower()

        if ext not in ALLOWED_EXTENSIONS:
            continue

        save_path = os.path.join(UPLOAD_DIR, filename)
        file.save(save_path)

        try:
            pdf_path = prepare_file(save_path, UPLOAD_DIR)
            meta = extract_metadata(pdf_path, doc_type)
            pending.append({
                "filename": filename,
                "pdf_path": pdf_path,
                "title": meta["title"],
                "author": meta["author"],
                "doc_type": doc_type
            })
        except Exception as e:
            print(f"Error preparing {filename}: {e}")

    session["pending"] = pending
    return jsonify({"pending": pending})

@app.route("/ingest/confirm", methods=["POST"])
def ingest_confirm():
    global _doc_cache
    confirmed = request.get_json()
    results = []

    for item in confirmed:
        try:
            pages = extract_pdf_text(item["pdf_path"])
            chunks = chunk_pages(
                pages,
                title=item["title"],
                author=item["author"],
                doc_type=item["doc_type"],
                source_file=os.path.basename(item["pdf_path"])
            )
            store_chunks(chunks)
            results.append({
                "filename": item["filename"],
                "status": "ingested",
                "title": item["title"],
                "author": item["author"],
                "doc_type": item["doc_type"]
            })
        except Exception as e:
            print(f"Error ingesting {item['filename']}: {e}")
            results.append({
                "filename": item["filename"],
                "status": "failed",
                "error": str(e)
            })

    _doc_cache = None
    return jsonify({"results": results})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
