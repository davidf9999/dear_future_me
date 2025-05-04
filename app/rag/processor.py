# app/rag/processor.py

from typing import Dict, Any
from langchain.schema import Document
from langchain.chains.retrieval_qa.base import RetrievalQA
from langchain_community.embeddings.openai import OpenAIEmbeddings
from langchain_community.vectorstores.chroma import Chroma

from app.core.config import get_settings


class DocumentProcessor:
    def __init__(self, namespace: str):
        cfg = get_settings()

        # ── Embeddings (stub-friendly) ────────────────────────────
        try:
            emb = OpenAIEmbeddings(openai_api_key=cfg.OPENAI_API_KEY)
        except TypeError:
            emb = OpenAIEmbeddings()

        # ── Vector store ──────────────────────────────────────────
        self.vectordb = Chroma(
            embedding_function=emb,
            collection_name=namespace,
            persist_directory=cfg.CHROMA_DIR,
        )

        # ── QA chain (stub-friendly) ──────────────────────────────
        retriever = self.vectordb.as_retriever()
        self.qa = RetrievalQA.from_chain_type(
            llm=None,  # test stub will override this
            retriever=retriever,
            chain_type="stuff",
        )

    def ingest_document(self, doc_id: str, text: str) -> None:
        self.vectordb.add_documents([{"text": text, "metadata": {"doc_id": doc_id}}])
        self.vectordb.persist()

    def query(self, query: str) -> str:
        # sync stub path (.run alias for .invoke)
        result = self.qa.run({"query": query})
        if isinstance(result, dict) and "result" in result:
            return result["result"]
        return str(result)
