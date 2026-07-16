"""Text chunking utilities for normalized document units."""
from typing import Any, Dict, List

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import DEFAULT_CHUNKING_STRATEGY, SUPPORTED_CHUNKING_STRATEGIES


class TextChunker:
    """Split document units into overlapping retrieval chunks."""

    @staticmethod
    def chunk_text(
        text: str,
        chunk_size: int = 800,
        chunk_overlap: int = 100,
    ) -> List[str]:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        return splitter.split_text(text)

    @staticmethod
    def chunk_pages(
        pages: List[Dict[str, Any]],
        chunk_size: int = 800,
        chunk_overlap: int = 100,
    ) -> List[Dict[str, Any]]:
        """Backward-compatible page chunking for existing PDF tests."""
        units = [
            {
                "unit_num": page["page_num"],
                "page_num": page["page_num"],
                "locator": f"page:{page['page_num']}",
                "locator_label": f"Page {page['page_num']}",
                "section_title": None,
                "sheet_name": None,
                "text": page["text"],
            }
            for page in pages
        ]
        return TextChunker.chunk_units(units, "pdf", chunk_size, chunk_overlap, "structure")

    @staticmethod
    def chunk_units(
        units: List[Dict[str, Any]],
        document_type: str,
        chunk_size: int = 800,
        chunk_overlap: int = 100,
        chunking_strategy: str = DEFAULT_CHUNKING_STRATEGY,
    ) -> List[Dict[str, Any]]:
        strategy = TextChunker._normalize_strategy(chunking_strategy, document_type)
        if strategy == "recursive":
            return TextChunker._chunk_combined(units, chunk_size, chunk_overlap)

        chunks = []
        chunk_id = 0
        for unit in units:
            unit_text = (unit.get("text") or "").strip()
            if not unit_text:
                continue
            if strategy == "table_rows" and document_type in {"csv", "xlsx"}:
                pieces = [unit_text]
            else:
                pieces = TextChunker.chunk_text(unit_text, chunk_size, chunk_overlap)
            for piece in pieces:
                chunks.append(TextChunker._chunk_payload(unit, chunk_id, piece))
                chunk_id += 1
        return chunks

    @staticmethod
    def _normalize_strategy(strategy: str, document_type: str) -> str:
        normalized = (strategy or DEFAULT_CHUNKING_STRATEGY).strip().lower()
        if normalized not in SUPPORTED_CHUNKING_STRATEGIES:
            raise ValueError(
                "chunking_strategy must be one of: "
                f"{', '.join(sorted(SUPPORTED_CHUNKING_STRATEGIES))}"
            )
        if normalized == "auto":
            return "table_rows" if document_type in {"csv", "xlsx"} else "structure"
        if normalized == "table_rows" and document_type not in {"csv", "xlsx"}:
            return "structure"
        return normalized

    @staticmethod
    def _chunk_combined(
        units: List[Dict[str, Any]],
        chunk_size: int,
        chunk_overlap: int,
    ) -> List[Dict[str, Any]]:
        combined_parts = []
        for unit in units:
            text = (unit.get("text") or "").strip()
            if not text:
                continue
            combined_parts.append(f"{unit.get('locator_label') or 'Document'}\n{text}")
        pieces = TextChunker.chunk_text("\n\n".join(combined_parts), chunk_size, chunk_overlap)
        document_unit = {
            "unit_num": 1,
            "page_num": next((unit.get("page_num") for unit in units if unit.get("page_num")), None),
            "locator": "document",
            "locator_label": "Document",
            "section_title": None,
            "sheet_name": None,
        }
        return [
            TextChunker._chunk_payload(document_unit, chunk_id, piece)
            for chunk_id, piece in enumerate(pieces)
        ]

    @staticmethod
    def _chunk_payload(unit: Dict[str, Any], chunk_id: int, text: str) -> Dict[str, Any]:
        preview = text[:150].replace("\n", " ")
        return {
            "page_num": unit.get("page_num"),
            "locator": unit.get("locator"),
            "locator_label": unit.get("locator_label") or "Document",
            "section_title": unit.get("section_title"),
            "sheet_name": unit.get("sheet_name"),
            "chunk_id": chunk_id,
            "text": text,
            "preview": preview,
        }
