# app/api/orchestrator.py

# app/api/orchestrator.py  ← replace existing Orchestrator with:

from langchain.chains import RetrievalQA
from langchain.llms import OpenAI
from app.rag.processor import DocumentProcessor
from app.core.settings import get_settings


class RagOrchestrator:
    def __init__(self):
        cfg = get_settings()
        # One processor per namespace
        self.theory_db = DocumentProcessor(cfg.CHROMA_NAMESPACE_THEORY)
        self.plan_db = DocumentProcessor(cfg.CHROMA_NAMESPACE_PLAN)
        self.session_db = DocumentProcessor(cfg.CHROMA_NAMESPACE_SESSION)
        # LLM for answering
        self.llm = OpenAI(model_name=cfg.LLM_MODEL, temperature=cfg.LLM_TEMPERATURE)

    async def answer(self, query: str) -> str:
        # 1) retrieve
        theory_chunks = self.theory_db.query(query, k=3)
        plan_chunks = self.plan_db.query(query, k=3)
        session_chunks = self.session_db.query(query, k=3)
        # 2) assemble context
        context = "\n\n".join(
            [c.page_content for c in (theory_chunks + plan_chunks + session_chunks)]
        )
        qa_chain = RetrievalQA(
            llm=self.llm,
            retriever=None,  # we do manual retrieval above
            chain_type="stuff",  # or map_reduce
        )
        return await qa_chain.arun({"query": query, "context": context})

    async def summarize_session(self, session_id: str):
        """Generate a summary of all session_data docs for this session."""
        docs = self.session_db.vectordb.get(where={"metadata.session_id": session_id})
        text = "\n\n".join(d.page_content for d in docs)
        summary = await self.llm.apredict(
            prompt=f"Summarize the following session:\n\n{text}"
        )
        # Index summary back into session_data
        self.session_db.ingest(
            f"summary_{session_id}",
            summary,
            metadata={"session_id": session_id, "type": "summary"},
        )
        return summary


# and swap in your FastAPI dependency:
def get_orchestrator() -> RagOrchestrator:
    return RagOrchestrator()


# TODO
# from langchain.llms import OpenAI
# from langchain.embeddings import OpenAIEmbeddings
# from langchain.vectorstores import Chroma
# from langchain.chains import RetrievalQA
# from app.core.settings import get_settings, Settings


# class Orchestrator:
#     def __init__(self):
#         cfg: Settings = get_settings()
#         emb = OpenAIEmbeddings(openai_api_key=cfg.OPENAI_API_KEY)
#         # Initialize vector store client
#         self.vectordb = Chroma(
#             embedding_function=emb,
#             collection_name=cfg.CHROMA_COLLECTION,
#             persist_directory=cfg.CHROMA_DIR,
#         )
#         # Build RetrievalQA chain
#         self.chain = RetrievalQA.from_chain_type(
#             llm=OpenAI(
#                 model_name=cfg.LLM_MODEL,
#                 temperature=cfg.LLM_TEMPERATURE,
#             ),
#             chain_type="stuff",
#             retriever=self.vectordb.as_retriever(),
#         )

#     async def answer(self, query: str) -> str:
#         return await self.chain.arun(query)


# # Dependency factory
# def get_orchestrator() -> Orchestrator:
#     return Orchestrator()
