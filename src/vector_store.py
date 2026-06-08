import os
import shutil

from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

from src.config import EMBEDDING_MODEL, TOP_K, CHROMA_PERSIST_DIRECTORY


def create_documents_from_chunks(chunks: list[dict]) -> list[Document]:
    """
    Convert chunk dictionaries into LangChain Document objects.
    """

    documents = []

    for chunk in chunks:
        document = Document(
            page_content=chunk["text"],
            metadata={
                "source": chunk["source"],
                "page": chunk["page"],
                "chunk_id": chunk["chunk_id"],
            },
        )

        documents.append(document)

    return documents


def create_vector_store(chunks: list[dict]) -> Chroma:
    """
    Create a Chroma vector store from text chunks.
    """

    documents = create_documents_from_chunks(chunks)

    embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)

    vector_store = Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        persist_directory=CHROMA_PERSIST_DIRECTORY,
    )

    vector_store.persist()
    return vector_store


def load_vector_store() -> Chroma | None:
    """
    Load an existing persistent Chroma vector store if it exists.
    """

    if not os.path.isdir(CHROMA_PERSIST_DIRECTORY):
        return None

    embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)
    vector_store = Chroma(
        persist_directory=CHROMA_PERSIST_DIRECTORY,
        embedding_function=embeddings,
    )

    return vector_store


def reset_vector_store() -> None:
    """
    Remove the local Chroma database directory to reset the index.
    """

    if os.path.isdir(CHROMA_PERSIST_DIRECTORY):
        shutil.rmtree(CHROMA_PERSIST_DIRECTORY)


def get_retriever(vector_store: Chroma, k: int = TOP_K, method: str = "similarity"):
    """
    Create a retriever from the vector store.

    Supports similarity search or MMR search depending on the method.
    """

    if method == "mmr":
        return vector_store.as_retriever(
            search_type="mmr",
            search_kwargs={"k": k, "fetch_k": max(k * 4, k)},
        )

    return vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={"k": k},
    )