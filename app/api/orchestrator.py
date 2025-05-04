# app/api/orchestrator.py

from fastapi import Request
from app.core.settings import get_settings
import pathlib


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

        # Embeddings (stub‐friendly)
        try:
            from langchain_community.embeddings.openai import OpenAIEmbeddings

            emb = OpenAIEmbeddings(openai_api_key=cfg.OPENAI_API_KEY)
        except Exception:
            emb = None

        # Vector store (stub‐friendly)
        try:
            from langchain_community.vectorstores.chroma import Chroma

            self.vectordb = Chroma(
                embedding_function=emb,
                collection_name=cfg.CHROMA_COLLECTION,
                persist_directory=cfg.CHROMA_DIR,
            )
        except Exception:
            self.vectordb = None

        # Retrieval QA chain with system prompt (stub‐friendly)
        try:
            from langchain.chains.retrieval_qa.base import RetrievalQA
            from langchain_community.chat_models import ChatOpenAI
            from langchain_core.prompts import PromptTemplate

            # Load our system prompt template
            prompt_path = (
                pathlib.Path(__file__).parent.parent / "prompts" / "system_prompt.md"
            )
            system_prompt = prompt_path.read_text(encoding="utf-8")
            prompt = PromptTemplate(
                template=system_prompt,
                input_variables=["context", "input"],
            )

            retriever = self.vectordb.as_retriever() if self.vectordb else None
            self.chain = RetrievalQA.from_chain_type(
                llm=ChatOpenAI(
                    model_name=cfg.LLM_MODEL,
                    temperature=cfg.LLM_TEMPERATURE,
                ),
                retriever=retriever,
                chain_type="stuff",
                return_source_documents=False,
                chain_type_kwargs={"prompt": prompt},
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
            # If anything goes wrong, apologize instead of echoing
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
