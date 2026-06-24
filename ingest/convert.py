import os
import subprocess
from config import ALLOWED_EXTENSIONS

def get_extension(filename):
    """Returns the lowercase file extension of a given filename."""
    return os.path.splitext(filename)[1].lower()

def is_allowed(filename):
    """Returns True if the file type is supported, False otherwise."""
    return get_extension(filename) in ALLOWED_EXTENSIONS

def convert_to_pdf(input_path, output_dir):
    """
    Converts a .docx or .pptx file to PDF using LibreOffice headless.
    Returns the path to the converted PDF, or raises an error if it fails.
    """
    ext = get_extension(input_path)

    if ext == ".pdf":
        return input_path  # already a PDF, nothing to do

    if ext not in [".docx", ".pptx"]:
        raise ValueError(f"Unsupported file type: {ext}")

    result = subprocess.run(
        ["libreoffice", "--headless", "--convert-to", "pdf",
         "--outdir", output_dir, input_path],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(f"LibreOffice conversion failed: {result.stderr}")

    base_name = os.path.splitext(os.path.basename(input_path))[0]
    pdf_path = os.path.join(output_dir, base_name + ".pdf")

    if not os.path.exists(pdf_path):
        raise RuntimeError(f"Conversion appeared to succeed but PDF not found: {pdf_path}")

    return pdf_path

def prepare_file(input_path, output_dir):
    """
    Main entry point for file preparation.
    Checks the file is allowed, converts if needed, returns a PDF path.
    """
    filename = os.path.basename(input_path)

    if not is_allowed(filename):
        ext = get_extension(filename)
        raise ValueError(
            f"'{ext}' files are not supported. "
            f"Accepted formats: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    return convert_to_pdf(input_path, output_dir)
