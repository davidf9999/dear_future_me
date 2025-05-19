# /home/dfront/code/dear_future_me/app/rag/processor.py
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
            client_settings=cfg.CHROMA_CLIENT_SETTINGS,
            persist_directory=cfg.CHROMA_DIR if not (cfg.CHROMA_HOST and cfg.CHROMA_PORT) else None,
        )

    def ingest(self, doc_id: str, text: str, metadata: dict | None = None) -> None:
        docs = [Document(page_content=text, metadata=metadata or {})]
        texts = self.text_splitter.split_documents(docs)
        # TODO: Add error handling for ChromaDB operations
        self.vectordb.add_documents(texts, ids=[f"{doc_id}_{i}" for i in range(len(texts))])
        # self.vectordb.persist() # REMOVE THIS LINE - Chroma client handles persistence

    def query(self, query: str, k: int = 5, metadata_filter: dict | None = None) -> List[Document]:
        # TODO: Add error handling for ChromaDB operations
        # TODO: Consider if metadata filtering should be part of the query
        return cast(List[Document], self.vectordb.similarity_search(query, k=k, filter=metadata_filter))

    def delete_collection(self) -> None:
        """Clears all documents from the collection associated with this namespace."""
        try:
            current_docs = self.vectordb.get()
            ids_to_delete = current_docs.get("ids", [])

            if ids_to_delete:
                self.vectordb.delete(ids=ids_to_delete)
                # self.vectordb.persist() # REMOVE THIS LINE if present in delete_collection too
                print(f"Cleared all documents from collection: {self.namespace}")
            else:
                print(f"Collection {self.namespace} was already empty or no documents found to delete.")

        except Exception as e:
            print(f"Error clearing documents from collection {self.namespace}: {e}")
