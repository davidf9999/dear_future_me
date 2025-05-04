# app/api/orchestrator.py

from fastapi import Request
from langchain.chains.retrieval_qa.base import RetrievalQA
from langchain_community.chat_models import ChatOpenAI
from app.core.settings import get_settings
from app.rag.processor import DocumentProcessor
from langchain_core.prompts import PromptTemplate

# Load system prompt template
SYSTEM_PROMPT = PromptTemplate.from_file("prompts/system.md")


def get_orchestrator() -> "Orchestrator":
    """
    Dependency factory returning a fresh Orchestrator.
    """
    return Orchestrator()


def get_rag_orchestrator(request: Request) -> "RagOrchestrator":
    """
    Dependency factory for the singleton RagOrchestrator in app.state.
    """
    orch = getattr(request.app.state, "rag_orchestrator", None)
    if orch is None:
        orch = RagOrchestrator()
        request.app.state.rag_orchestrator = orch
    return orch


class Orchestrator:
    """
    Manages a retrieval-augmented QA chain with a system prompt.
    """

    def __init__(self):
        cfg = get_settings()

        # Initialize embeddings (stub-friendly)
        emb = None
        try:
            from langchain_community.embeddings.openai import OpenAIEmbeddings

            emb = OpenAIEmbeddings(openai_api_key=cfg.OPENAI_API_KEY)
        except Exception:
            pass

        # Initialize vector store and retriever (stub-friendly)
        retriever = None
        try:
            from langchain_community.vectorstores.chroma import Chroma

            vectordb = Chroma(
                embedding_function=emb,
                collection_name=cfg.CHROMA_COLLECTION,
                persist_directory=cfg.CHROMA_DIR,
            )
            retriever = vectordb.as_retriever()
        except Exception:
            pass

        # Build the RetrievalQA chain with system prompt
        try:
            self.chain = RetrievalQA.from_chain_type(
                llm=ChatOpenAI(
                    model_name=cfg.LLM_MODEL,
                    temperature=cfg.LLM_TEMPERATURE,
                ),
                retriever=retriever,
                chain_type="stuff",
                combine_prompt=SYSTEM_PROMPT,
            )
        except Exception:

            class _StubChain:
                async def arun(self, q: str) -> str:
                    raise RuntimeError("chain not available")

            self.chain = _StubChain()

    async def answer(self, query: str) -> str:
        """
        Produce an answer using arun; fallback to echo on error.
        """
        try:
            return await self.chain.arun(query)
        except Exception:
            return f"Echo: {query}"


class RagOrchestrator:
    """
    Manages separate RAG namespaces for theory, plan, and session.
    """

    def __init__(self):
        cfg = get_settings()
        self.theory_db = DocumentProcessor(cfg.CHROMA_NAMESPACE_THEORY)
        self.plan_db = DocumentProcessor(cfg.CHROMA_NAMESPACE_PLAN)
        self.session_db = DocumentProcessor(cfg.CHROMA_NAMESPACE_SESSION)

    async def summarize_session(self, session_id: str) -> str:
        try:
            return await self.session_db.qa.arun(session_id)
        except Exception:
            return f"Summary for {session_id}"
