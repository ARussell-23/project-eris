import os
import fitz
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

def get_all_documents():
    """
    Walks the document folders and returns metadata for every PDF found.
    Pulls title/author from embedded PDF metadata with filename fallback.
    """
    import chromadb
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    try:
        collection = client.get_collection(COLLECTION_NAME)
        chunk_count = collection.count()
    except Exception:
        chunk_count = 0

    docs = []
    for folder, doc_type in FOLDER_TYPE_MAP.items():
        if not os.path.exists(folder):
            continue
        for filename in sorted(os.listdir(folder)):
            if not filename.endswith(".pdf"):
                continue
            pdf_path = os.path.join(folder, filename)
            try:
                pdf = fitz.open(pdf_path)
                meta = pdf.metadata
                page_count = len(pdf)
                pdf.close()
                title = (meta.get("title") or "").strip() or os.path.splitext(filename)[0].replace("_", " ").replace("-", " ").title()
                author = (meta.get("author") or "").strip()
            except Exception:
                title = filename
                author = ""
                page_count = 0

            docs.append({
                "filename": filename,
                "filepath": pdf_path,
                "doc_type": doc_type,
                "title": title,
                "author": author,
                "pages": page_count
            })

    return docs, chunk_count

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

    return jsonify({"results": results})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
