import os
import sqlite3
from flask import Flask, render_template, request, jsonify, session, send_file, abort, Response, stream_with_context
from guide.response import ask_guide_stream
from ingest.convert import prepare_file
from ingest.metadata import extract_metadata
from ingest.pdf_extract import extract_pdf_text
from ingest.chunker import chunk_pages
from ingest.store import store_chunks, get_collection
from config import UPLOAD_DIR, ALLOWED_EXTENSIONS, BOOKS_DIR, ARTICLES_DIR, DOCS_DIR, CHROMA_DIR, COLLECTION_NAME
import json

app = Flask(__name__)
app.secret_key = "eris-local-secret"

os.makedirs(UPLOAD_DIR, exist_ok=True)

FOLDER_TYPE_MAP = {
    BOOKS_DIR: "BOOK",
    ARTICLES_DIR: "ARTICLE",
    DOCS_DIR: "DOCUMENT"
}

SQLITE_PATH = "data/search_index.db"

_doc_cache = None
_chunk_count_cache = None

def get_all_documents():
    global _doc_cache, _chunk_count_cache
    if _doc_cache is not None:
        return _doc_cache, _chunk_count_cache
    try:
        conn = sqlite3.connect(SQLITE_PATH)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM chunks")
        chunk_count = c.fetchone()[0]
        c.execute("SELECT source_file, title, author, doc_type FROM chunks GROUP BY source_file")
        meta_lookup = {row[0]: {"title": row[1], "author": row[2], "doc_type": row[3]} for row in c.fetchall()}
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
    try:
        conn = sqlite3.connect(SQLITE_PATH)
        c = conn.cursor()
        c.execute("SELECT title, author, doc_type FROM chunks WHERE source_file = ? LIMIT 1", (filename,))
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

@app.route("/search")
def search():
    query = request.args.get("q", "").strip()

    def empty_stream():
        yield f"data: {json.dumps({'type': 'results', 'results': []})}\n\n"
        yield f"data: {json.dumps({'type': 'token', 'token': 'Nothing to search on. What are you looking for?'})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    if not query:
        return Response(stream_with_context(empty_stream()), mimetype="text/event-stream")

    def generate():
        try:
            for chunk in ask_guide_stream(query):
                yield chunk
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )

@app.route("/archive")
def archive():
    return render_template("archive.html")

@app.route("/archive/documents")
def archive_documents():
    docs, chunk_count = get_all_documents()
    return jsonify({"documents": docs, "total": len(docs), "chunks": chunk_count})

@app.route("/archive/doc/<path:filename>")
def archive_doc(filename):
    return render_template("doc.html")

@app.route("/archive/doc-metadata/<path:filename>")
def archive_doc_metadata(filename):
    docs, _ = get_all_documents()
    match = next((d for d in docs if d["filename"] == filename), None)
    if not match:
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

@app.route("/archive/search")
def archive_search():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"results": [], "total": 0})
    try:
        conn = sqlite3.connect(SQLITE_PATH)
        c = conn.cursor()
        c.execute("""
            SELECT chunks.source_file, chunks.title, chunks.author, chunks.doc_type,
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
        results = [{"source_file": r[0], "title": r[1], "author": r[2], "doc_type": r[3],
                    "page_number": r[4], "snippet": r[5]} for r in rows]
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
    new_doc_type = data.get("doc_type", "").strip().upper()

    if not filename:
        return jsonify({"success": False, "error": "No filename provided"})

    try:
        import chromadb
        client = chromadb.PersistentClient(path=CHROMA_DIR)
        collection = client.get_collection(COLLECTION_NAME)
        results = collection.get(where={"source_file": filename}, include=["metadatas"])

        if not results["ids"]:
            return jsonify({"success": False, "error": "No chunks found for this file"})

        current_doc_type = results["metadatas"][0].get("doc_type", "")
        new_filename = filename

        # Handle file move if doc type changed
        if new_doc_type and new_doc_type != current_doc_type:
            type_to_folder = {
                "BOOK": BOOKS_DIR,
                "ARTICLE": ARTICLES_DIR,
                "DOCUMENT": DOCS_DIR
            }
            new_folder = type_to_folder.get(new_doc_type)
            if new_folder:
                # Find current file location
                current_path = None
                for folder in [BOOKS_DIR, ARTICLES_DIR, DOCS_DIR]:
                    candidate = os.path.join(folder, filename)
                    if os.path.exists(candidate):
                        current_path = candidate
                        break

                if current_path:
                    new_path = os.path.join(new_folder, filename)
                    if current_path != new_path:
                        os.rename(current_path, new_path)

        # Update ChromaDB
        updated_metadatas = [{**meta, "title": title, "author": author,
                              "doc_type": new_doc_type or meta.get("doc_type")}
                             for meta in results["metadatas"]]
        ids = results["ids"]
        batch_size = 5000
        for i in range(0, len(ids), batch_size):
            collection.update(ids=ids[i:i+batch_size], metadatas=updated_metadatas[i:i+batch_size])

        # Update SQLite
        conn = sqlite3.connect(SQLITE_PATH)
        c = conn.cursor()
        c.execute("""
            UPDATE chunks SET title = ?, author = ?, doc_type = ?
            WHERE source_file = ?
        """, (title, author, new_doc_type or current_doc_type, filename))
        c.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')")
        conn.commit()
        conn.close()

        _doc_cache = None
        return jsonify({
            "success": True,
            "chunks_updated": len(ids),
            "new_filename": new_filename
        })
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
                "filename": filename, "pdf_path": pdf_path,
                "title": meta["title"], "author": meta["author"], "doc_type": doc_type
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
            chunks = chunk_pages(pages, title=item["title"], author=item["author"],
                                 doc_type=item["doc_type"], source_file=os.path.basename(item["pdf_path"]))
            store_chunks(chunks)
            results.append({"filename": item["filename"], "status": "ingested",
                            "title": item["title"], "author": item["author"], "doc_type": item["doc_type"]})
        except Exception as e:
            print(f"Error ingesting {item['filename']}: {e}")
            results.append({"filename": item["filename"], "status": "failed", "error": str(e)})

    _doc_cache = None
    return jsonify({"results": results})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
