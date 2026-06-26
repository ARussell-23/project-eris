# Changelog

## v0.3.0 — 2026-06-25

### Added
- **Streaming responses in G.U.I.D.E.** — responses now appear word by word with a blinking cursor; result cards appear immediately while Ollama generates, eliminating the long wait
- **Document type editor** — doc type (BOOK / ARTICLE / DOCUMENT) is now editable on the document page; changing type moves the file to the correct folder automatically and updates ChromaDB and SQLite
- **`eris.local` hostname** — ERIS is now accessible at `http://eris.local:5000` on the local network, works across both home WiFi and hotspot mode
- **Hotspot auto-detect** — Pi automatically switches to hotspot mode (SSID: ERIS) when no known WiFi network is found on boot; manual toggle scripts available as backup (`hotspot_on.sh`, `hotspot_off.sh`)

### Fixed
- Removed debug print statements from `guide/response.py`

---

## v0.2.0 — 2026-06-25

### Added
- **A.R.C.H.I.V.E. Browse tab** — full document list with filter by type (BOOK / ARTICLE / DOCUMENT) and text filter by title, author, or filename
- **A.R.C.H.I.V.E. Search tab** — keyword full-text search across all indexed document content using SQLite FTS5; results link directly to the relevant page in the document
- **Document page** (`/archive/doc/<filename>`) — dedicated page per document with embedded PDF viewer, download button, and editable title/author metadata
- **Metadata editor** — edit title and author directly on the document page; saves to both ChromaDB and SQLite immediately
- **G.U.I.D.E. page links** — page number buttons in search results now link to the document page at the correct page
- **SQLite full-text search index** — `build_search_index.py` builds a persistent FTS5 index from ChromaDB data; `store.py` updates SQLite automatically on every future ingest
- **Resumable bulk ingestion** — `bulk_ingest.py` saves progress after each file and resumes from where it left off if interrupted
- **Dark mode** — persists across all screens via localStorage
- **Systemd service** — ERIS runs on boot with automatic Ollama model warm-up

### Fixed
- ChromaDB batch size error on large documents — `store.py` now splits storage into batches of 5000 chunks
- ARCHIVE document list now loads from SQLite (fast) rather than querying ChromaDB per file (slow)
- Empty PDF handling — files with no extractable text are caught and skipped gracefully

### Collection
- 451 documents indexed (378 books, 27 articles, 46 documents)
- 893,716 chunks in ChromaDB and SQLite
- 17 image-based PDFs skipped (no text layer)

---

## v0.1.0 — 2026-06-24
Initial release — POC running on Raspberry Pi 5

### Added
- G.U.I.D.E. — semantic search interface powered by Mistral 7B via Ollama
- A.R.C.H.I.V.E. — document browser with type filtering and inline PDF viewing
- I.N.G.E.S.T. — upload pipeline with file conversion (PDF/DOCX/PPTX), hybrid metadata extraction, and user confirmation before indexing
- ChromaDB vector index with sentence-aware chunking via NLTK
- Folder-based bulk ingestion script with metadata flagging
- MIT license
