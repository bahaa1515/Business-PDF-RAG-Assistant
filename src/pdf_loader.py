import fitz  # PyMuPDF
from typing import BinaryIO


def load_pdf_pages(uploaded_file: BinaryIO) -> list[dict]:
    """
    Extract text from each page of an uploaded PDF file.

    Returns a list of dictionaries.
    Each dictionary contains:
    - text: extracted page text
    - page: page number starting from 1
    - source: original filename
    """

    pages = []

    # Read the uploaded file bytes
    pdf_bytes = uploaded_file.read()

    # Open PDF from bytes
    pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")

    for page_index, page in enumerate(pdf_document):
        text = page.get_text()

        # Skip empty pages
        if text and text.strip():
            pages.append(
                {
                    "text": text.strip(),
                    "page": page_index + 1,
                    "source": uploaded_file.name,
                }
            )

    pdf_document.close()

    return pages