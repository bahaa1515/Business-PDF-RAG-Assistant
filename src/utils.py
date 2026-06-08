"""Utility helpers for formatting and text context generation."""


def format_source_preview(document, preview_length: int = 300) -> str:
    """Return a cleaned preview string for a retrieved source document."""
    preview = document.page_content[:preview_length].replace("\n", " ")
    return preview.strip()


def format_retrieval_debug_chunk(document, rank: int, preview_length: int = 400) -> str:
    """Format a retrieved chunk for debug display."""
    source = document.metadata.get("source", "Unknown source")
    page = document.metadata.get("page", "Unknown page")
    chunk_id = document.metadata.get("chunk_id", "N/A")
    preview = document.page_content[:preview_length].replace("\n", " ").strip()

    return (
        f"Rank {rank}\n"
        f"Source: {source}\n"
        f"Page: {page}\n"
        f"Chunk ID: {chunk_id}\n"
        f"Preview: {preview}..."
    )


def format_documents_for_context(documents) -> str:
    """Create a single context string from retrieved document metadata."""
    context_parts = []

    for i, doc in enumerate(documents, start=1):
        source = doc.metadata.get("source", "Unknown source")
        page = doc.metadata.get("page", "Unknown page")

        context_parts.append(
            f"[Source {i}: {source}, page {page}]\n{doc.page_content}"
        )

    return "\n\n".join(context_parts)


def extract_sources_metadata(documents) -> list:
    """Return a simple list of source metadata dicts for storage or evaluation."""
    out = []
    for d in documents:
        out.append(
            {
                'source': d.metadata.get('source'),
                'page': d.metadata.get('page'),
                'chunk_id': d.metadata.get('chunk_id'),
            }
        )
    return out
