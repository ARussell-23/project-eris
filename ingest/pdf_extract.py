import fitz

def extract_pdf_text(pdf_path):
    """
    Opens a PDF and extracts text from every page.
    Returns a list of dictionaries, one per page, with page number and text.
    """
    doc = fitz.open(pdf_path)
    pages = []

    for page_num in range(len(doc)):
        page_text = doc[page_num].get_text()
        pages.append({
            "page_number": page_num + 1,
            "text": page_text
        })

    doc.close()
    return pages
