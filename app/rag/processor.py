# app/rag/processor.py

from langchain.schema import Document
from langchain_community.embeddings.openai import OpenAIEmbeddings
from langchain_community.vectorstores.chroma import Chroma

from app.core.settings import get_settings


class DocumentProcessor:
    def __init__(self, namespace: str):
        cfg = get_settings()
        try:
            emb = OpenAIEmbeddings(openai_api_key=cfg.OPENAI_API_KEY)
        except TypeError:
            emb = OpenAIEmbeddings()
        self.vectordb = Chroma(
            embedding_function=emb,
            collection_name=namespace,
            persist_directory=cfg.CHROMA_DIR,
        )

    def ingest(self, doc_id: str, text: str, metadata: dict | None = None) -> None:
        """Ingest a piece of text under doc_id."""
        self.vectordb.add_documents([{"text": text, "metadata": metadata or {}}])
        self.vectordb.persist()

    def query(self, query: str, k: int = 5) -> list[Document]:
        """Return up to k matching Documents for `query`."""
        return self.vectordb.similarity_search(query, k=k)
