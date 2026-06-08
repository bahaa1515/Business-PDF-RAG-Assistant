import fitz  # PyMuPDF
from typing import BinaryIO, Any


def load_pdf_pages(uploaded_file: Any) -> list[dict]:
    """
    Extract text from each page of an uploaded PDF file.

    `uploaded_file` can be either:
    - a file-like object with `.read()` and `.name` (the Streamlit upload object), or
    - a dict with keys `name` and `bytes` (for stored in-session byte blobs).

    Returns a list of dictionaries. Each dictionary contains:
    - text: extracted page text
    - page: page number starting from 1
    - source: original filename
    """

    pages = []

    # Support dict inputs (name + bytes) for re-indexing experiments
    if isinstance(uploaded_file, dict) and "bytes" in uploaded_file:
        pdf_bytes = uploaded_file["bytes"]
        source_name = uploaded_file.get("name", "uploaded.pdf")
    else:
        # Assume file-like object
        pdf_bytes = uploaded_file.read()
        source_name = getattr(uploaded_file, "name", "uploaded.pdf")

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
                    "source": source_name,
                }
            )

    pdf_document.close()

    return pages