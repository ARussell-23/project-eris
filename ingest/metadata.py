import os
import fitz
from config import ALLOWED_EXTENSIONS

def extract_metadata(pdf_path, doc_type):
    """
    Attempts to extract title and author from a PDF's embedded metadata.
    Falls back to parsing the filename if metadata is missing or incomplete.
    Returns a dictionary with title, author, doc_type, and source filename.
    """
    filename = os.path.basename(pdf_path)
    doc = fitz.open(pdf_path)
    embedded = doc.metadata
    doc.close()

    title = _clean(embedded.get("title"))
    author = _clean(embedded.get("author"))

    if not title:
        title = _title_from_filename(filename)

    if not author:
        author = _author_from_filename(filename)

    return {
        "title": title or "",
        "author": author or "",
        "doc_type": doc_type,
        "source_file": filename
    }

def _clean(value):
    """
    Strips whitespace from a metadata string.
    Returns None if the value is empty, whitespace-only, or missing.
    """
    if not value:
        return None
    cleaned = value.strip()
    return cleaned if cleaned else None

def _title_from_filename(filename):
    """
    Attempts to extract a readable title from a filename.
    Removes the extension, replaces underscores and hyphens with spaces.
    """
    name = os.path.splitext(filename)[0]
    name = name.replace("_", " ").replace("-", " ")
    return name.title()

def _author_from_filename(filename):
    """
    Attempts to extract an author name from a filename.
    Looks for patterns like 'smith_2019' or 'smith_jones_2019'
    where the last segment is a 4-digit year.
    Returns None if no year pattern is found.
    """
    name = os.path.splitext(filename)[0]
    parts = name.replace("-", "_").split("_")

    if len(parts) >= 2 and parts[-1].isdigit() and len(parts[-1]) == 4:
        author_parts = parts[:-1]
        return " & ".join(p.title() for p in author_parts)

    return None
