from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma


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

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

    vector_store = Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
    )

    return vector_store


def get_retriever(vector_store: Chroma, k: int = 4):
    """
    Create a retriever from the vector store.

    k means how many relevant chunks to retrieve for each question.
    """

    return vector_store.as_retriever(
        search_kwargs={"k": k}
    )