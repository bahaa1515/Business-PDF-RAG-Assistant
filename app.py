import os
import streamlit as st
from dotenv import load_dotenv

from src.pdf_loader import load_pdf_pages
from src.text_splitter import split_pages_into_chunks
from src.vector_store import create_vector_store, get_retriever
from src.rag_chain import answer_question


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


def process_uploaded_pdfs(uploaded_files):
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

    chunks = split_pages_into_chunks(all_pages)

    if not chunks:
        raise ValueError("No text chunks were created from the uploaded PDFs.")

    vector_store = create_vector_store(chunks)
    retriever = get_retriever(vector_store)

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
        preview = doc.page_content[:300].replace("\n", " ")

        with st.expander(f"Source {i}: {source} — page {page}"):
            st.write(preview + "...")


def main():
    st.title("Business PDF RAG Assistant")
    st.write(
        "Upload PDF documents, ask questions, and get answers based only on the uploaded files."
    )

    if not check_api_key():
        st.error(
            "OpenAI API key is missing. Add it to your .env file as OPENAI_API_KEY."
        )
        st.stop()

    if "retriever" not in st.session_state:
        st.session_state.retriever = None

    if "processed_files" not in st.session_state:
        st.session_state.processed_files = []

    with st.sidebar:
        st.header("Upload documents")

        uploaded_files = st.file_uploader(
            "Upload one or more PDFs",
            type=["pdf"],
            accept_multiple_files=True,
        )

        process_button = st.button("Process documents")

        if process_button:
            if not uploaded_files:
                st.warning("Please upload at least one PDF file.")
            else:
                try:
                    with st.spinner("Processing PDFs..."):
                        retriever, page_count, chunk_count = process_uploaded_pdfs(
                            uploaded_files
                        )

                        st.session_state.retriever = retriever
                        st.session_state.processed_files = [
                            uploaded_file.name for uploaded_file in uploaded_files
                        ]

                    st.success(
                        f"Processed {len(uploaded_files)} file(s), "
                        f"{page_count} page(s), and {chunk_count} chunk(s)."
                    )

                except Exception as e:
                    st.error(f"Error while processing documents: {e}")

        if st.session_state.processed_files:
            st.subheader("Processed files")
            for file_name in st.session_state.processed_files:
                st.write(f"- {file_name}")

    st.divider()

    question = st.chat_input("Ask a question about your uploaded PDFs")

    if question:
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