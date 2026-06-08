import os
import streamlit as st
from dotenv import load_dotenv

from src.pdf_loader import load_pdf_pages
from src.text_splitter import split_pages_into_chunks
from src.vector_store import (
    create_vector_store,
    get_retriever,
    load_vector_store,
    reset_vector_store,
)
from src.config import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_RETRIEVAL_METHOD,
    RETRIEVAL_METHOD_OPTIONS,
    TOP_K,
)
from src.rag_chain import answer_question
from src.utils import format_source_preview


load_dotenv()


st.set_page_config(
    page_title="Business PDF RAG Assistant",
    page_icon="📄",
    layout="wide",
)


def check_api_key() -> bool:
    """
    Check if OpenAI API key exists.
    """

    return bool(os.getenv("OPENAI_API_KEY"))


def process_uploaded_pdfs(
    uploaded_files,
    chunk_size: int,
    chunk_overlap: int,
    top_k: int,
    retrieval_method: str,
):
    """
    Process uploaded PDFs:
    1. Load pages
    2. Split into chunks
    3. Create vector store
    4. Create retriever
    """

    all_pages = []

    for uploaded_file in uploaded_files:
        pages = load_pdf_pages(uploaded_file)
        all_pages.extend(pages)

    if not all_pages:
        raise ValueError(
            "No text could be extracted from the uploaded PDFs. "
            "They may be scanned PDFs or empty files."
        )

    chunks = split_pages_into_chunks(
        all_pages,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    if not chunks:
        raise ValueError("No text chunks were created from the uploaded PDFs.")

    vector_store = create_vector_store(chunks)
    retriever = get_retriever(
        vector_store,
        k=top_k,
        method=retrieval_method,
    )

    return retriever, len(all_pages), len(chunks)


def display_sources(sources):
    """
    Display retrieved source documents with filename, page, and preview.
    """

    if not sources:
        st.warning("No sources were retrieved.")
        return

    st.subheader("Sources")

    for i, doc in enumerate(sources, start=1):
        source = doc.metadata.get("source", "Unknown source")
        page = doc.metadata.get("page", "Unknown page")
        preview = format_source_preview(doc)

        with st.expander(f"Source {i}: {source} — page {page}"):
            st.write(preview + "...")


def main():
    st.title("Business PDF RAG Assistant")
    st.write(
        "Upload PDF documents, ask questions, and get answers based only on the uploaded files."
    )

    api_key_present = check_api_key()

    if not api_key_present:
        st.warning(
            "OpenAI API key is missing. Add it to your .env file as OPENAI_API_KEY. "
            "You can still view the app layout, but document processing and question answering will stay disabled until the API key is added."
        )

    if "retriever" not in st.session_state:
        st.session_state.retriever = None

    if "processed_files" not in st.session_state:
        st.session_state.processed_files = []

    if "chunk_size" not in st.session_state:
        st.session_state.chunk_size = DEFAULT_CHUNK_SIZE

    if "chunk_overlap" not in st.session_state:
        st.session_state.chunk_overlap = DEFAULT_CHUNK_OVERLAP

    if "top_k" not in st.session_state:
        st.session_state.top_k = TOP_K

    if "retrieval_method" not in st.session_state:
        st.session_state.retrieval_method = DEFAULT_RETRIEVAL_METHOD

    if "saved_settings" not in st.session_state:
        st.session_state.saved_settings = {
            "chunk_size": st.session_state.chunk_size,
            "chunk_overlap": st.session_state.chunk_overlap,
            "top_k": st.session_state.top_k,
            "retrieval_method": st.session_state.retrieval_method,
        }

    if api_key_present and st.session_state.retriever is None:
        existing_vector_store = load_vector_store()
        if existing_vector_store is not None:
            st.session_state.retriever = get_retriever(
                existing_vector_store,
                k=st.session_state.top_k,
                method=st.session_state.retrieval_method,
            )
            st.info("Loaded existing vector store from local disk.")

    with st.sidebar:
        st.header("Upload documents")

        uploaded_files = st.file_uploader(
            "Upload one or more PDFs",
            type=["pdf"],
            accept_multiple_files=True,
        )

        st.subheader("RAG settings")

        st.session_state.chunk_size = st.number_input(
            "Chunk size",
            min_value=100,
            max_value=2000,
            value=st.session_state.chunk_size,
            step=50,
            key="chunk_size",
        )

        st.session_state.chunk_overlap = st.number_input(
            "Chunk overlap",
            min_value=0,
            max_value=1000,
            value=st.session_state.chunk_overlap,
            step=25,
            key="chunk_overlap",
        )

        st.session_state.top_k = st.number_input(
            "Top K retrieval",
            min_value=1,
            max_value=20,
            value=st.session_state.top_k,
            step=1,
            key="top_k",
        )

        st.session_state.retrieval_method = st.selectbox(
            "Retrieval method",
            options=RETRIEVAL_METHOD_OPTIONS,
            index=RETRIEVAL_METHOD_OPTIONS.index(st.session_state.retrieval_method),
            key="retrieval_method",
        )

        settings_changed = (
            st.session_state.chunk_size != st.session_state.saved_settings["chunk_size"]
            or st.session_state.chunk_overlap != st.session_state.saved_settings["chunk_overlap"]
            or st.session_state.top_k != st.session_state.saved_settings["top_k"]
            or st.session_state.retrieval_method != st.session_state.saved_settings["retrieval_method"]
        )

        if settings_changed and st.session_state.processed_files:
            st.warning(
                "RAG settings changed. Please reprocess your documents to update the index."
            )

        process_button = st.button("Process documents")

        if process_button:
            if not uploaded_files:
                st.warning("Please upload at least one PDF file.")
            elif not api_key_present:
                st.warning(
                    "OpenAI API key is missing. Add OPENAI_API_KEY to your .env file "
                    "before processing documents."
                )
            else:
                try:
                    with st.spinner("Processing PDFs..."):
                        retriever, page_count, chunk_count = process_uploaded_pdfs(
                            uploaded_files,
                            chunk_size=st.session_state.chunk_size,
                            chunk_overlap=st.session_state.chunk_overlap,
                            top_k=st.session_state.top_k,
                            retrieval_method=st.session_state.retrieval_method,
                        )

                        st.session_state.retriever = retriever
                        st.session_state.processed_files = [
                            uploaded_file.name for uploaded_file in uploaded_files
                        ]
                        st.session_state.saved_settings = {
                            "chunk_size": st.session_state.chunk_size,
                            "chunk_overlap": st.session_state.chunk_overlap,
                            "top_k": st.session_state.top_k,
                            "retrieval_method": st.session_state.retrieval_method,
                        }

                    st.success(
                        f"Processed {len(uploaded_files)} file(s), "
                        f"{page_count} page(s), and {chunk_count} chunk(s)."
                    )

                except Exception as e:
                    st.error(f"Error while processing documents: {e}")

        if st.button("Reset vector store"):
            reset_vector_store()
            st.session_state.retriever = None
            st.session_state.processed_files = []
            st.success("Local Chroma vector store has been reset.")

        if st.session_state.processed_files:
            st.subheader("Processed files")
            for file_name in st.session_state.processed_files:
                st.write(f"- {file_name}")

    st.divider()

    question = st.chat_input("Ask a question about your uploaded PDFs")

    if question:
        if not api_key_present:
            st.warning(
                "OpenAI API key is missing. Add it to your .env file as OPENAI_API_KEY "
                "before asking questions."
            )
            return

        if st.session_state.retriever is None:
            st.warning("Please upload and process PDF documents first.")
            return

        with st.chat_message("user"):
            st.write(question)

        try:
            with st.spinner("Searching documents and generating answer..."):
                result = answer_question(
                    question=question,
                    retriever=st.session_state.retriever,
                )

            with st.chat_message("assistant"):
                st.write(result["answer"])

            display_sources(result["sources"])

        except Exception as e:
            st.error(f"Error while answering question: {e}")


if __name__ == "__main__":
    main()