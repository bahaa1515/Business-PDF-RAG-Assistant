from langchain_openai import ChatOpenAI

from src.config import MODEL_NAME, REFUSAL_MESSAGE, RETRIEVAL_SCORE_THRESHOLD
from src.prompts import RAG_PROMPT
from src.utils import format_documents_for_context
import time


def answer_question(question: str, retriever) -> dict:
    """
    Answer a user question using retrieved document chunks.

    Returns:
    - answer: generated answer
    - sources: retrieved source documents
    """

    # 1. Retrieve relevant chunks
    start = time.perf_counter()
    retrieved_docs = retriever.invoke(question)

    # If no documents were retrieved, return the refusal message immediately.
    if not retrieved_docs:
        return {
            "answer": REFUSAL_MESSAGE,
            "sources": [],
            "latency_seconds": time.perf_counter() - start,
        }

    # 2. Format retrieved chunks as context
    context = format_documents_for_context(retrieved_docs)

    # Optionally filter retrieved docs by a score threshold if available.
    if RETRIEVAL_SCORE_THRESHOLD is not None:
        filtered = []
        for d in retrieved_docs:
            score = None
            # Some retrievers place score in metadata, others expose attribute
            if isinstance(d.metadata, dict) and "score" in d.metadata:
                score = d.metadata.get("score")
            elif hasattr(d, "score"):
                score = getattr(d, "score")

            if score is None or score >= RETRIEVAL_SCORE_THRESHOLD:
                filtered.append(d)

        retrieved_docs = filtered

    # 3. Create the LLM
    llm = ChatOpenAI(
        model=MODEL_NAME,
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

    # If the model followed instructions to refuse, return the exact refusal message.
    content = response.content.strip()
    latency = time.perf_counter() - start

    if REFUSAL_MESSAGE in content:
        return {
            "answer": REFUSAL_MESSAGE,
            "sources": [],
            "latency_seconds": latency,
        }

    # Normal answer
    return {
        "answer": content,
        "sources": retrieved_docs,
        "latency_seconds": latency,
    }