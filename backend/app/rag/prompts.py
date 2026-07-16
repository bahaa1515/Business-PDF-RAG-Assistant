"""
RAG prompt templates.
Strict grounded prompts that ensure answers use only retrieved context.
"""
from langchain_core.prompts import ChatPromptTemplate

from app.rag.prompt_variants import get_system_prompt

# System prompt for grounded RAG. The live pipeline uses AnswerGenerator directly,
# but this template stays aligned for future LangChain integrations.
SYSTEM_PROMPT = get_system_prompt("grounded_complete")

# RAG prompt template
RAG_PROMPT_TEMPLATE = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", """Context from documents:
{context}

Question: {question}

Answer:""")
])


def get_rag_prompt():
    """Get the RAG prompt template."""
    return RAG_PROMPT_TEMPLATE
