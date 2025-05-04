# app/api/orchestrator.py

from langchain.llms import OpenAI
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from langchain.chains import RetrievalQA
from app.core.settings import get_settings, Settings

from app.rag.processor import DocumentProcessor


class Orchestrator:
    """
    Original simple QA orchestrator hitting a single Chroma collection.
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


class RagOrchestrator:
    """
    Multi-namespace RAG orchestrator:
      - retrieves from theory, personal_plan, and session_data
      - merges context into a single prompt
      - answers via the LLM
      - can summarize a session and re-index the summary
    """

    def __init__(self):
        cfg = get_settings()
        # Three distinct vector stores (namespaces)
        self.theory_db = DocumentProcessor(cfg.CHROMA_NAMESPACE_THEORY)
        self.plan_db = DocumentProcessor(cfg.CHROMA_NAMESPACE_PLAN)
        self.session_db = DocumentProcessor(cfg.CHROMA_NAMESPACE_SESSION)

        # Single LLM for both QA and summary
        self.llm = OpenAI(
            model_name=cfg.LLM_MODEL,
            temperature=cfg.LLM_TEMPERATURE,
        )

    async def answer(self, query: str) -> str:
        # 1) Retrieve top-3 chunks from each namespace
        theory_chunks = self.theory_db.query(query, k=3)
        plan_chunks = self.plan_db.query(query, k=3)
        session_chunks = self.session_db.query(query, k=3)

        # 2) Merge into one context
        all_chunks = theory_chunks + plan_chunks + session_chunks
        context = "\n\n".join(chunk.page_content for chunk in all_chunks)

        # 3) Run a simple RetrievalQA chain on the merged context
        chain = RetrievalQA(
            llm=self.llm,
            retriever=None,  # we already retrieved
            chain_type="stuff",
        )
        return await chain.arun({"query": query, "context": context})

    async def summarize_session(self, session_id: str) -> str:
        # 1) Fetch all docs for this session
        hits = self.session_db.vectordb.get(where={"metadata.session_id": session_id})
        text = "\n\n".join(doc.page_content for doc in hits)

        # 2) Ask the LLM to summarize
        summary = await self.llm.apredict(f"Summarize the following session:\n\n{text}")

        # 3) Index the summary back into session_data namespace
        self.session_db.ingest(
            f"summary_{session_id}",
            summary,
            metadata={"session_id": session_id, "type": "summary"},
        )
        return summary


def get_orchestrator() -> RagOrchestrator:
    """
    FastAPI dependency factory for RagOrchestrator.
    """
    return RagOrchestrator()
