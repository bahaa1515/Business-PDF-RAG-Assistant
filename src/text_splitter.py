from langchain_text_splitters import RecursiveCharacterTextSplitter

def split_pages_into_chunks(
    pages: list[dict],
    chunk_size: int = 800,
    chunk_overlap: int = 150,
) -> list[dict]:
    """
    Split extracted PDF pages into smaller text chunks.

    Each chunk keeps its metadata:
    - source filename
    - page number
    - chunk id
    """

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ".", " ", ""],
    )

    chunks = []

    for page in pages:
        page_text = page["text"]
        source = page["source"]
        page_number = page["page"]

        split_texts = text_splitter.split_text(page_text)

        for chunk_index, chunk_text in enumerate(split_texts):
            chunks.append(
                {
                    "text": chunk_text,
                    "source": source,
                    "page": page_number,
                    "chunk_id": f"{source}-page-{page_number}-chunk-{chunk_index + 1}",
                }
            )

    return chunks