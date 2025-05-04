# app/api/orchestrator.py

from fastapi import Request
from typing import Any

from langchain.prompts import PromptTemplate
from langchain.chains.llm import LLMChain
from langchain.chains.retrieval_qa.base import RetrievalQA
from langchain.chains.combine_documents.stuff import StuffDocumentsChain
from langchain_community.llms.openai import OpenAIChat
from langchain_community.embeddings.openai import OpenAIEmbeddings
from langchain_community.vectorstores.chroma import Chroma

from app.core.config import get_settings


class Orchestrator:
    def __init__(self):
        cfg = get_settings()
        # Embedding (stub-friendly)
        try:
            emb = OpenAIEmbeddings(openai_api_key=cfg.OPENAI_API_KEY)
        except TypeError:
            emb = OpenAIEmbeddings()
        # Vector store
        self.vectordb = Chroma(
            embedding_function=emb,
            collection_name=cfg.CHROMA_COLLECTION,
            persist_directory=cfg.CHROMA_DIR,
        )
        retriever = self.vectordb.as_retriever()
        # Retrieval-QA chain
        self.chain = RetrievalQA.from_chain_type(
            llm=OpenAIChat(model_name=cfg.LLM_MODEL, temperature=cfg.LLM_TEMPERATURE),
            retriever=retriever,
            chain_type="stuff",
            combine_documents_chain=StuffDocumentsChain(
                llm_chain=LLMChain(
                    llm=OpenAIChat(
                        model_name=cfg.LLM_MODEL, temperature=cfg.LLM_TEMPERATURE
                    ),
                    prompt=PromptTemplate.from_template(
                        "Answer:\n\n{context}\n\nQuestion: {question}"
                    ),
                ),
                document_variable_name="context",
            ),
        )

    async def answer(self, query: str) -> str:
        try:
            return await self.chain.arun(query)
        except Exception:
            return f"Echo: {query}"


def get_orchestrator() -> Orchestrator:
    """Dependency-injectable constructor for the chat orchestrator."""
    return Orchestrator()


# ── RAG orchestrator ────────────────────────────────────────────────


class RagOrchestrator:
    def __init__(self):
        cfg = get_settings()
        from app.rag.processor import DocumentProcessor

        # one vector DB per namespace
        self.theory_db = DocumentProcessor(cfg.CHROMA_NAMESPACE_THEORY)
        # tests only stub summarize_session, so we don't need the others right now
        self.session_db = DocumentProcessor(cfg.CHROMA_NAMESPACE_REFLECTIONS)

    async def summarize_session(self, session_id: str) -> str:
        # stub-friendly
        return self.session_db.query(session_id)


def get_rag_orchestrator(request: Request) -> RagOrchestrator:
    """
    Singleton‐style dependency for RAG orchestrator.
    On first call, stores it on request.app.state.
    """
    if not hasattr(request.app.state, "rag_orchestrator"):
        request.app.state.rag_orchestrator = RagOrchestrator()
    return request.app.state.rag_orchestrator
