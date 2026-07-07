# ERIS — Evidence Retrieval & Inquiry System

A fully local document retrieval system built on the principle that a good system should retrieve and cite, not summarize and synthesize.

ERIS is a librarian, not a synthesizer. It surfaces relevant passages from a personal document collection with precise citations and returns control to the researcher.

Everything runs on local hardware. No documents or queries leave the machine.

A special thank you to Mo Goltz who kindly donated his expansive design library to build ERIS. This project wouldn't exist without it.

---

## Modules

### G.U.I.D.E. — Guided Understanding through Indexed Document Exploration
Semantic search interface powered by a locally-hosted Mistral model via Ollama. Surfaces relevant passages with source citations. Responses stream word by word. Operates within a defined persona: precise, dry, comfortable returning nothing when nothing genuinely matches. Queries are silently expanded into multiple semantic variants before retrieval.

### A.R.C.H.I.V.E. — Aggregated Reference Collection: Housed in an Indexed Vault for Evidence
Browsable document library with two modes:
- **Browse** — filter by document type (BOOK / ARTICLE / DOCUMENT), search by title, author, or filename
- **Search** — keyword full-text search across all indexed content, results link directly to the relevant page

Each document has a dedicated page with an embedded PDF viewer, download button, and editable metadata (title, author, type). Changing document type moves the file to the correct folder automatically.

### I.N.G.E.S.T. — Intake, Normalization & Generation of Embedded Source Text
Document processing pipeline and upload interface. Accepts PDF, DOCX, and PPTX files. Extracts text via PyMuPDF, chunks with NLTK sentence-aware splitting, generates embeddings via Sentence Transformers, and stores vectors in ChromaDB and SQLite. Metadata is extracted automatically and confirmed by the user before indexing.

---

## Design Decisions

**Privacy by architecture.** Documents and queries never leave the machine — not as a feature, but as a structural guarantee. There is no external service to configure, audit, or trust.

**Transparency over confidence.** Because AI can hallucinate and obscure its sources, ERIS returns passages with precise citations rather than synthesised answers. Null results are valid outputs — not failures to be papered over.

**Assistive, not autonomous.** ERIS surfaces what is in the collection and returns control to the researcher. Analysis, interpretation, and conclusion remain human work.

---

## Tech Stack

| Component | Tool |
|---|---|
| PDF extraction | PyMuPDF |
| Text chunking | nltk (punkt_tab, sentence-aware) |
| Embeddings | Sentence Transformers (BAAI/bge-small-en-v1.5) |
| Vector store | ChromaDB (persistent) |
| Full-text search | SQLite FTS5 |
| LLM inference | Ollama (local) |
| LLM model | mistral:7b-instruct |
| File conversion | LibreOffice headless |
| Web framework | Flask |

---

## Hardware

- **Tested on:** Raspberry Pi 5, 8GB RAM, Raspberry Pi OS Bookworm 64-bit
- **Should work on:** any machine with sufficient RAM to run an Ollama model locally. More RAM and a capable CPU or GPU will significantly improve response times.
- **Access:** available at `http://eris.local:5000` on the local network

---

## Setup

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com) installed and running
- LibreOffice (for DOCX/PPTX conversion): `sudo apt install libreoffice --no-install-recommends`
- Mistral model pulled: `ollama pull mistral:7b-instruct`

### Install

```bash
git clone https://github.com/ARussell-23/project-eris.git
cd project-eris

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

### Download NLTK data

```bash
python3 -c "import nltk; nltk.download('punkt_tab')"
```

### Configure

Edit `config.py` to set your paths and preferences. Key settings:

- `OLLAMA_MODEL` — model name (default: `mistral:7b-instruct`)
- `OLLAMA_BASE_URL` — Ollama server URL (default: `http://localhost:11434`)
- `NULL_THRESHOLD` — minimum similarity score to surface a result (default: `0.3`)
- `CHUNK_SIZE` — max characters per chunk (default: `400`)

### Add documents

Place PDFs in the appropriate subfolder:

```
documents/books/
documents/articles/
documents/documents/
```

### Build the search index

Run once after bulk ingestion to build the SQLite full-text search index:

```bash
python3 build_search_index.py
```

### Index

```bash
python3 bulk_ingest.py
```

Review any flagged metadata in the generated `flagged_metadata_*.csv` file.

### Run

```bash
python3 app.py
```

Open `http://localhost:5000` in your browser.

---

## Running as a System Service (Linux)

```bash
sudo nano /etc/systemd/system/eris.service
```

```ini
[Unit]
Description=Project ERIS
After=network.target ollama.service

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/path/to/project_eris
ExecStart=/path/to/project_eris/venv/bin/python3 /path/to/project_eris/app.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable eris
sudo systemctl start eris
```

---

## Hotspot Mode (optional, Linux)

ERIS can broadcast its own WiFi network when no known network is available — useful for travel or offline use. Requires `hostapd` and `dnsmasq`.

### Install

```bash
sudo apt install hostapd dnsmasq -y
```

### Configure hostapd

```bash
sudo nano /etc/hostapd/hostapd.conf
```

```ini
interface=wlan0
driver=nl80211
ssid=ERIS
hw_mode=g
channel=7
wpa=2
wpa_passphrase=YOUR_PASSWORD
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
```

```bash
sudo nano /etc/default/hostapd
# Set: DAEMON_CONF="/etc/hostapd/hostapd.conf"
```

### Configure dnsmasq

Add to `/etc/dnsmasq.conf`:

```ini
interface=wlan0
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
address=/eris.local/192.168.4.1
```

### Auto-detect script

Create `~/check_wifi.sh`:

```bash
#!/bin/bash
sleep 30
if iwgetid wlan0 --raw | grep -q "."; then
    exit 0
fi
ip addr add 192.168.4.1/24 dev wlan0
systemctl start hostapd
systemctl start dnsmasq
```

```bash
chmod +x ~/check_wifi.sh
```

Create `/etc/systemd/system/eris-wifi.service`:

```ini
[Unit]
Description=ERIS WiFi auto-detect
After=network.target

[Service]
Type=oneshot
ExecStart=/home/YOUR_USERNAME/check_wifi.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable eris-wifi
```

In hotspot mode, ERIS is accessible at `http://eris.local:5000` after connecting to the ERIS WiFi network.

---

## Project Structure

```
project_eris/
├── app.py                  # Flask application and routes
├── config.py               # All configurable parameters
├── bulk_ingest.py          # Resumable batch ingestion script
├── build_search_index.py   # One-time SQLite FTS index builder
├── ingest/
│   ├── chunker.py          # Sentence-aware text chunking
│   ├── convert.py          # File filtering and conversion
│   ├── metadata.py         # Title/author extraction
│   ├── pdf_extract.py      # PDF text extraction
│   └── store.py            # Embedding, ChromaDB and SQLite storage
├── retrieval/
│   └── search.py           # Semantic vector search with query expansion
├── guide/
│   ├── prompt.py           # GUIDE system prompt and citation formatting
│   └── response.py         # Ollama LLM orchestration with streaming
├── templates/
│   ├── landing.html        # E.R.I.S. landing page
│   ├── index.html          # G.U.I.D.E. search interface
│   ├── archive.html        # A.R.C.H.I.V.E. document browser
│   ├── doc.html            # Document page with viewer and metadata editor
│   └── ingest.html         # I.N.G.E.S.T. upload interface
├── docs/
│   ├── ERIS_concept_v2.md  # System design document
│   └── GUIDE_persona_samples.md  # GUIDE persona stress tests
└── requirements.txt
```

---

## Concept Documents

- [`docs/ERIS_concept_v2.md`](docs/ERIS_concept_v2.md) — full system design and philosophy
- [`docs/GUIDE_persona_samples.md`](docs/GUIDE_persona_samples.md) — GUIDE persona stress tests with on-voice and overshoot examples

---

## Roadmap

- [ ] Scale to larger document collections
- [ ] Migrate to more capable hardware for faster inference
- [ ] Zotero metadata integration for bulk filename normalization

---

## Development Notes

Project ERIS was designed and built by Andrew Russell using Claude (Anthropic) as the primary development partner. Andrew conceived the system, defined the architecture and design philosophy, made all product decisions, and directed the build throughout. Claude wrote the code, provided technical guidance, and worked through implementation problems in real time — functioning less as a tool and more as a collaborator.

---

## License

MIT
