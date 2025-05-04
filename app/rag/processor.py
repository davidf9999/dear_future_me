# app/rag/processor.py

from typing import List, Dict
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from app.core.settings import get_settings


class DocumentProcessor:
    def __init__(self, namespace: str):
        cfg = get_settings()
        emb = OpenAIEmbeddings(openai_api_key=cfg.OPENAI_API_KEY)
        self.vectordb = Chroma(
            embedding_function=emb,
            collection_name=namespace,
            persist_directory=cfg.CHROMA_DIR,
        )
        # Splits into ~2–4 sentence chunks
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=400, chunk_overlap=50, separators=["\n\n", "\n", ".", "!", "?"]
        )

    def ingest(self, doc_id: str, text: str, metadata: Dict = None):
        """Chunk, embed, and add to vector store."""
        chunks = self.splitter.split_text(text)
        # build list of dicts for upsert
        docs = [
            {"id": f"{doc_id}_{i}", "text": chunk, "metadata": metadata or {}}
            for i, chunk in enumerate(chunks)
        ]
        self.vectordb.add_documents(docs)
        self.vectordb.persist()

    def query(self, q: str, k: int = 5):
        """Retrieve top-k chunks for query q."""
        return self.vectordb.similarity_search(q, k=k)
