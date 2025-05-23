# /home/dfront/code/dear_future_me/app/rag/processor.py
# Full file content
import logging
from typing import Any, Dict, List, Optional

import chromadb.config
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

from app.core.settings import get_settings

cfg = get_settings()
logger = logging.getLogger(__name__)


class DocumentProcessor:
    def __init__(
        self,
        namespace: str,
        embedding_model: str = cfg.EMBEDDING_MODEL,
        persist_directory: str = cfg.CHROMA_PERSIST_DIR,  # Use CHROMA_PERSIST_DIR from settings
        chroma_host: Optional[str] = cfg.CHROMA_HOST,  # Use CHROMA_HOST from settings
        chroma_port: Optional[int] = cfg.CHROMA_PORT,  # Use CHROMA_PORT from settings
    ):
        self.namespace = namespace
        self.embedding_function = OpenAIEmbeddings(model=embedding_model)

        # Construct client_settings based on whether host/port are provided
        if chroma_host and chroma_port:
            # Ensure port is a string for chromadb.config.Settings
            client_settings_obj = chromadb.config.Settings(
                chroma_api_impl="chromadb.api.fastapi.FastAPI",
                chroma_server_host=chroma_host,
                chroma_server_http_port=str(chroma_port),
                anonymized_telemetry=False,  # Optional: disable telemetry if desired
            )
            logger.info(f"DocumentProcessor '{namespace}' connecting to Chroma server at {chroma_host}:{chroma_port}")
        else:
            client_settings_obj = chromadb.config.Settings(
                is_persistent=True,
                persist_directory=persist_directory,
                anonymized_telemetry=False,  # Optional: disable telemetry if desired
            )
            logger.info(f"DocumentProcessor '{namespace}' using persistent Chroma at {persist_directory}")

        self.vectordb = Chroma(
            collection_name=namespace,
            embedding_function=self.embedding_function,
            persist_directory=persist_directory
            if not (chroma_host and chroma_port)
            else None,  # Only set persist_directory for local
            client_settings=client_settings_obj,
        )

    def ingest(self, doc_id: str, text: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Ingests a single text document."""
        doc = Document(page_content=text, metadata=metadata or {})
        try:
            self.vectordb.add_documents([doc], ids=[doc_id])
            logger.info(f"Successfully ingested document ID '{doc_id}' into namespace '{self.namespace}'.")
        except Exception as e:
            logger.error(f"Failed to ingest document ID '{doc_id}' into namespace '{self.namespace}': {e}")
            raise

    def ingest_batch(
        self, texts: List[str], doc_ids: List[str], metadatas: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """Ingests a batch of text documents."""
        if not metadatas:
            metadatas = [{} for _ in texts]
        elif len(texts) != len(metadatas):
            raise ValueError("Length of texts and metadatas must match.")
        if len(texts) != len(doc_ids):
            raise ValueError("Length of texts and doc_ids must match.")

        documents = [Document(page_content=text, metadata=md) for text, md in zip(texts, metadatas)]
        try:
            self.vectordb.add_documents(documents, ids=doc_ids)
            logger.info(f"Successfully ingested batch of {len(documents)} documents into namespace '{self.namespace}'.")
        except Exception as e:
            logger.error(f"Failed to ingest batch of documents into namespace '{self.namespace}': {e}")
            raise

    def query(self, query: str, k: int = 5, metadata_filter: Optional[Dict[str, Any]] = None) -> List[Document]:
        """Queries the vector store for similar documents."""
        try:
            results = self.vectordb.similarity_search(query, k=k, filter=metadata_filter)
            logger.info(f"Query '{query[:50]}...' in namespace '{self.namespace}' returned {len(results)} documents.")
            return results
        except Exception as e:
            logger.error(f"Failed to query namespace '{self.namespace}' with query '{query[:50]}...': {e}")
            return []

    def delete_documents(self, doc_ids: List[str]) -> None:
        """Deletes documents by their IDs."""
        try:
            self.vectordb.delete(ids=doc_ids)
            logger.info(f"Attempted to delete documents with IDs {doc_ids} from namespace '{self.namespace}'.")
        except Exception as e:
            logger.error(f"Failed to delete documents with IDs {doc_ids} from namespace '{self.namespace}': {e}")
            raise

    def get_collection_count(self) -> int:
        """Returns the number of documents in the collection."""
        try:
            count = self.vectordb._collection.count()
            logger.info(f"Namespace '{self.namespace}' contains {count} documents.")
            return count
        except Exception as e:
            logger.error(f"Failed to get document count for namespace '{self.namespace}': {e}")
            return 0

    def persist(self) -> None:
        """Persists the vector store to disk if it's a persistent client."""
        # Chroma client with Http behöver inte persist().
        # Chroma client with persist_directory hanterar persistens automatiskt vid skrivningar
        # eller vid __del__ om is_persistent=True och en persist_directory är satt.
        # Denna metod kan behållas för explicit kontroll om det behövs i framtiden,
        # men är oftast inte nödvändig med nuvarande Chroma-klient.
        if self.vectordb._client_settings.is_persistent and self.vectordb._client_settings.persist_directory:
            logger.info(
                f"Attempting to persist namespace '{self.namespace}' to {self.vectordb._client_settings.persist_directory} (Chroma handles this automatically)."
            )
            # self.vectordb.persist() # Chroma's persist() is often implicit or handled by client settings
        else:
            logger.info(
                f"Namespace '{self.namespace}' is not configured for explicit persistence via this method (e.g., remote client)."
            )
