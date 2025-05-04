# app/api/orchestrator.py

from fastapi import Request
from langchain.llms import OpenAI
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from langchain.chains import RetrievalQA
from app.core.settings import get_settings, Settings
from app.rag.processor import DocumentProcessor

# ─── Simple QA Orchestrator ───────────────────────────────────────────


class Orchestrator:
    """
    Original single-namespace QA for /chat/text.
    """

    def __init__(self):
        cfg: Settings = get_settings()
        emb = OpenAIEmbeddings(openai_api_key=cfg.OPENAI_API_KEY)
        self.vectordb = Chroma(
            embedding_function=emb,
            collection_name=cfg.CHROMA_COLLECTION,
            persist_directory=cfg.CHROMA_DIR,
        )
        self.chain = RetrievalQA.from_chain_type(
            llm=OpenAI(
                model_name=cfg.LLM_MODEL,
                temperature=cfg.LLM_TEMPERATURE,
            ),
            chain_type="stuff",
            retriever=self.vectordb.as_retriever(),
        )

    async def answer(self, query: str) -> str:
        return await self.chain.arun(query)


def get_orchestrator() -> Orchestrator:
    """
    Dependency factory for the simple Orchestrator.
    """
    return Orchestrator()


# ─── Multi‐Namespace RAG Orchestrator ─────────────────────────────────


class RagOrchestrator:
    """
    RAG orchestrator that handles theory/personal_plan/session_data.
    """

    def __init__(self):
        cfg = get_settings()
        self.theory_db = DocumentProcessor(cfg.CHROMA_NAMESPACE_THEORY)
        self.plan_db = DocumentProcessor(cfg.CHROMA_NAMESPACE_PLAN)
        self.session_db = DocumentProcessor(cfg.CHROMA_NAMESPACE_SESSION)

        self.llm = OpenAI(
            model_name=cfg.LLM_MODEL,
            temperature=cfg.LLM_TEMPERATURE,
        )

    async def answer(self, query: str) -> str:
        # retrieve
        t = self.theory_db.query(query, k=3)
        p = self.plan_db.query(query, k=3)
        s = self.session_db.query(query, k=3)

        # build context
        context = "\n\n".join(chunk.page_content for chunk in (t + p + s))

        # QA on merged context
        chain = RetrievalQA(
            llm=self.llm,
            retriever=None,
            chain_type="stuff",
        )
        return await chain.arun({"query": query, "context": context})

    async def summarize_session(self, session_id: str) -> str:
        hits = self.session_db.vectordb.get(where={"metadata.session_id": session_id})
        text = "\n\n".join(doc.page_content for doc in hits)
        summary = await self.llm.apredict(f"Summarize this session:\n\n{text}")
        # re‐index summary
        self.session_db.ingest(
            f"summary_{session_id}",
            summary,
            metadata={"session_id": session_id, "type": "summary"},
        )
        return summary


def get_rag_orchestrator(request: Request) -> RagOrchestrator:
    """
    Dependency factory for the singleton RagOrchestrator in app.state.
    """
    # First call: initialize and stash on app.state
    if not hasattr(request.app.state, "rag_orchestrator"):
        request.app.state.rag_orchestrator = RagOrchestrator()
    # Every subsequent call returns the same instance
    return request.app.state.rag_orchestrator
