import nltk
from config import CHUNK_SIZE, CHUNK_OVERLAP

def chunk_pages(pages, title, author, doc_type, source_file):
    """
    Takes a list of pages (from pdf_extract.py) and splits them into
    sentence-aware chunks. Attaches citation metadata to every chunk.
    Returns a list of chunk dictionaries ready for embedding and storage.
    """
    chunks = []

    for page in pages:
        page_chunks = _chunk_text(page["text"])
        for chunk_text in page_chunks:
            if chunk_text.strip():
                chunks.append({
                    "text": chunk_text.strip(),
                    "page_number": page["page_number"],
                    "title": title,
                    "author": author,
                    "doc_type": doc_type,
                    "source_file": source_file
                })

    return chunks

def _chunk_text(text):
    """
    Splits a block of text into sentence-aware chunks.
    Respects CHUNK_SIZE as a ceiling and adds CHUNK_OVERLAP between chunks.
    Overlap is trimmed to the nearest word boundary.
    """
    sentences = nltk.sent_tokenize(text)
    chunks = []
    current_chunk = ""

    for sentence in sentences:
        if len(current_chunk) + len(sentence) <= CHUNK_SIZE:
            current_chunk += " " + sentence
        else:
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
            overlap_raw = current_chunk[-CHUNK_OVERLAP:] if len(current_chunk) > CHUNK_OVERLAP else current_chunk
            overlap = overlap_raw[overlap_raw.find(" ")+1:] if " " in overlap_raw else overlap_raw
            current_chunk = overlap + " " + sentence

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks
