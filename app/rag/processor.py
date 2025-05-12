# app/rag/processor.py
from typing import List, cast

from langchain.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

from app.core.settings import get_settings

cfg = get_settings()


class DocumentProcessor:
    def __init__(self, namespace: str):
        self.namespace = namespace
        self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        self.embeddings = OpenAIEmbeddings(api_key=cfg.OPENAI_API_KEY)
        self.vectordb = Chroma(
            collection_name=self.namespace,
            embedding_function=self.embeddings,
            persist_directory=cfg.CHROMA_DIR,  # Uses the settings value
        )

    def ingest(self, doc_id: str, text: str, metadata: dict | None = None) -> None:
        docs = [Document(page_content=text, metadata=metadata or {})]
        texts = self.text_splitter.split_documents(docs)
        # TODO: Add error handling for ChromaDB operations
        self.vectordb.add_documents(texts, ids=[f"{doc_id}_{i}" for i in range(len(texts))])
        self.vectordb.persist()

    def query(self, query: str, k: int = 5, metadata_filter: dict | None = None) -> List[Document]:
        # TODO: Add error handling for ChromaDB operations
        # TODO: Consider if metadata filtering should be part of the query
        # results = self.vectordb.similarity_search_with_score(query, k=k, filter=metadata_filter)
        return cast(List[Document], self.vectordb.similarity_search(query, k=k, filter=metadata_filter))

    def delete_collection(self) -> None:
        """Deletes the entire collection associated with this namespace."""
        try:
            # Note: Chroma's delete_collection might not exist on older versions or specific client instances.
            # This is a conceptual representation. Check ChromaDB documentation for the correct method.
            # For instance, you might need to delete by IDs or clear the collection in another way.
            # If using the HTTP client, it would be an API call.
            # If using the Python client directly, it might be:
            if hasattr(self.vectordb, "_collection") and hasattr(self.vectordb._collection, "delete"):
                print(f"Attempting to delete collection: {self.namespace}")
                # This is a common pattern but might vary:
                # self.vectordb._client.delete_collection(name=self.namespace)
                # Or if the vectordb object itself has a delete_collection method:
                # self.vectordb.delete_collection()
                # For now, let's assume we clear documents if direct deletion is complex
                ids_to_delete = self.vectordb.get(include=[])["ids"]  # Get all IDs
                if ids_to_delete:
                    self.vectordb.delete(ids=ids_to_delete)
                    self.vectordb.persist()
                    print(f"Cleared all documents from collection: {self.namespace}")
                else:
                    print(f"Collection {self.namespace} was already empty or does not exist.")

            else:
                print(
                    f"Warning: Direct collection deletion method not found for {self.namespace}. Documents may persist if not cleared manually."
                )
        except Exception as e:
            print(f"Error deleting collection {self.namespace}: {e}")
            # Depending on Chroma version, specific exceptions might be caught.
