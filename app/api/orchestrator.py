# app/api/orchestrator.py

from fastapi import Request
from app.core.settings import get_settings


def get_orchestrator() -> "Orchestrator":
    return Orchestrator()


def get_rag_orchestrator(request: Request) -> "RagOrchestrator":
    orch = getattr(request.app.state, "rag_orchestrator", None)
    if orch is None:
        orch = RagOrchestrator()
        request.app.state.rag_orchestrator = orch
    return orch


class Orchestrator:
    def __init__(self):
        cfg = get_settings()

        # 1) Embeddings (stub-friendly)
        try:
            # From the standalone langchain-openai package
            from langchain_openai import OpenAIEmbeddings

            emb = OpenAIEmbeddings(openai_api_key=cfg.OPENAI_API_KEY)
        except Exception:
            emb = None

        # 2) Vector store (stub-friendly)
        try:
            # From the standalone langchain-chroma package
            from langchain_chroma import Chroma

            self.vectordb = Chroma(
                embedding_function=emb,
                collection_name=cfg.CHROMA_COLLECTION,
                persist_directory=cfg.CHROMA_DIR,
            )
        except Exception:
            self.vectordb = None

        # 3) Retrieval QA chain (stub-friendly)
        try:
            from langchain.chains.retrieval_qa.base import RetrievalQA

            # From the langchain-community chat_models
            from langchain_community.chat_models import ChatOpenAI

            retriever = self.vectordb.as_retriever() if self.vectordb else None
            self.chain = RetrievalQA.from_chain_type(
                llm=ChatOpenAI(
                    model_name=cfg.LLM_MODEL,
                    temperature=cfg.LLM_TEMPERATURE,
                ),
                retriever=retriever,
                chain_type="stuff",
            )
        except Exception:

            class _StubChain:
                async def arun(self, q: str) -> str:
                    raise RuntimeError("chain not available")

            self.chain = _StubChain()

    async def answer(self, query: str) -> str:
        try:
            return await self.chain.arun(query)
        except Exception:
            # On real-mode failure, inform rather than echo
            return "I’m sorry, I’m unable to answer that right now. Please try again later."


class RagOrchestrator:
    def __init__(self):
        cfg = get_settings()
        from app.rag.processor import DocumentProcessor

        self.theory_db = DocumentProcessor(cfg.CHROMA_NAMESPACE_THEORY)
        self.plan_db = DocumentProcessor(cfg.CHROMA_NAMESPACE_PLAN)
        self.session_db = DocumentProcessor(cfg.CHROMA_NAMESPACE_SESSION)

    async def summarize_session(self, session_id: str) -> str:
        try:
            return await self.session_db.qa.arun(session_id)
        except Exception:
            return f"Summary for {session_id}"
