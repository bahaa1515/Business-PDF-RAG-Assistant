from langchain_openai import ChatOpenAI
from src.prompts import RAG_PROMPT


def format_documents_for_context(documents) -> str:
    """
    Convert retrieved documents into one context string for the LLM.
    """

    context_parts = []

    for i, doc in enumerate(documents, start=1):
        source = doc.metadata.get("source", "Unknown source")
        page = doc.metadata.get("page", "Unknown page")

        context_parts.append(
            f"[Source {i}: {source}, page {page}]\n{doc.page_content}"
        )

    return "\n\n".join(context_parts)


def answer_question(question: str, retriever) -> dict:
    """
    Answer a user question using retrieved document chunks.

    Returns:
    - answer: generated answer
    - sources: retrieved source documents
    """

    # 1. Retrieve relevant chunks
    retrieved_docs = retriever.invoke(question)

    # 2. Format retrieved chunks as context
    context = format_documents_for_context(retrieved_docs)

    # 3. Create the LLM
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
    )

    # 4. Build the final prompt
    prompt = RAG_PROMPT.invoke(
        {
            "context": context,
            "question": question,
        }
    )

    # 5. Ask the LLM
    response = llm.invoke(prompt)

    return {
        "answer": response.content,
        "sources": retrieved_docs,
    }