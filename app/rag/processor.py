# app/rag/processor.py
# app/rag/processor.py
import logging
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings
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
        persist_directory: str = cfg.CHROMA_PERSIST_DIR,
        chroma_host: Optional[str] = cfg.CHROMA_HOST,
        chroma_port: Optional[int] = cfg.CHROMA_PORT,
    ):
        self.namespace = namespace
        self.embedding_function = OpenAIEmbeddings(model=embedding_model)

        # Create client settings based on whether we're using a remote or local Chroma
        if chroma_host and chroma_port:
            # Remote Chroma server
            client_settings = ChromaSettings(
                chroma_api_impl="rest",
                chroma_server_host=chroma_host,
                chroma_server_http_port=str(chroma_port),
                anonymized_telemetry=False,
            )
            logger.info(f"Connecting to Chroma server at {chroma_host}:{chroma_port}")
            self.vectordb = Chroma(
                collection_name=namespace,
                embedding_function=self.embedding_function,
                client_settings=client_settings,
            )
        else:
            # Local Chroma with persistence
            client_settings = ChromaSettings(
                is_persistent=True,
                persist_directory=persist_directory,
                anonymized_telemetry=False,
            )
            logger.info(f"Using persistent Chroma at {persist_directory}")

            # Ensure the persist directory exists
            import os

            os.makedirs(persist_directory, exist_ok=True)

            # Initialize Chroma with the new API
            client = chromadb.PersistentClient(path=persist_directory, settings=client_settings)

            # Delete existing collection if it exists to avoid dimension mismatch
            try:
                client.delete_collection(namespace)
                logger.info(f"Deleted existing collection '{namespace}' to avoid dimension mismatch")
            except Exception as e:
                logger.debug(f"Could not delete collection (may not exist): {e}")

            # Create new collection
            self.vectordb = Chroma(
                collection_name=namespace,
                embedding_function=self.embedding_function,
                client=client,
                persist_directory=persist_directory,
            )

    # [Rest of your DocumentProcessor methods remain the same]
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
        # Chroma with persist_directory handles persistence automatically
        # We don't need to do anything here as the client handles it
        logger.info(f"Persist called for namespace '{self.namespace}'. Chroma handles persistence automatically.")
        # No need to call persist() as Chroma handles it automatically
        pass

    # def persist(self) -> None:
    #     """Persists the vector store to disk if it's a persistent client."""
    #     # Chroma client with Http behöver inte persist().
    #     # Chroma client with persist_directory hanterar persistens automatiskt vid skrivningar
    #     # eller vid __del__ om is_persistent=True och en persist_directory är satt.
    #     # Denna metod kan behållas för explicit kontroll om det behövs i framtiden,
    #     # men är oftast inte nödvändig med nuvarande Chroma-klient.
    #     if self.vectordb._client_settings.is_persistent and self.vectordb._client_settings.persist_directory:
    #         logger.info(
    #             f"Attempting to persist namespace '{self.namespace}' to {self.vectordb._client_settings.persist_directory} (Chroma handles this automatically)."
    #         )
    #         # self.vectordb.persist() # Chroma's persist() is often implicit or handled by client settings
    #     else:
    #         logger.info(
    #             f"Namespace '{self.namespace}' is not configured for explicit persistence via this method (e.g., remote client)."
    #         )
