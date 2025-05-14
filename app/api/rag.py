# app/api/rag.py
import logging  # Add logging
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse
from langchain.schema import Document

from app.api.orchestrator import RagOrchestrator, get_orchestrator
from app.core.settings import get_settings
from app.rag.processor import (
    DocumentProcessor,  # Import DocumentProcessor for type hint
)

# Load configuration
cfg = get_settings()
router = APIRouter(tags=["rag"])


# Define allowed namespaces for ingestion
ALLOWED_NAMESPACES = Literal[
    cfg.CHROMA_NAMESPACE_THEORY,
    cfg.CHROMA_NAMESPACE_PLAN,
    cfg.CHROMA_NAMESPACE_SESSION,
    cfg.CHROMA_NAMESPACE_FUTURE,
    cfg.CHROMA_NAMESPACE_THERAPIST_NOTES,
    cfg.CHROMA_NAMESPACE_CHAT_HISTORY,
]


@router.post("/ingest/")
async def ingest_document(
    namespace: ALLOWED_NAMESPACES = Form(...),
    file: UploadFile = File(...),
    orchestrator: RagOrchestrator = Depends(get_orchestrator),
):
    """
    Ingests a document into the specified RAG namespace.
    The document is identified by its filename.
    """
    try:
        contents = await file.read()
        text = contents.decode("utf-8")

        dp_instance: Optional[DocumentProcessor] = None  # Type hint for clarity
        if namespace == cfg.CHROMA_NAMESPACE_THEORY:
            dp_instance = orchestrator.theory_db
        elif namespace == cfg.CHROMA_NAMESPACE_PLAN:
            dp_instance = orchestrator.plan_db
        elif namespace == cfg.CHROMA_NAMESPACE_SESSION:
            dp_instance = orchestrator.session_db
        elif namespace == cfg.CHROMA_NAMESPACE_FUTURE:
            dp_instance = orchestrator.future_db
        elif namespace == cfg.CHROMA_NAMESPACE_THERAPIST_NOTES:
            dp_instance = orchestrator.therapist_notes_db
        elif namespace == cfg.CHROMA_NAMESPACE_CHAT_HISTORY:
            dp_instance = orchestrator.chat_history_db

        if not dp_instance:
            # This case should ideally not be reached due to Literal validation
            logging.error(f"Document processor not configured for validated namespace: {namespace}")
            raise HTTPException(
                status_code=500, detail=f"Internal error: Document processor not configured for namespace: {namespace}"
            )

        metadata = {"source": file.filename, "namespace": namespace}
        # Consider adding user_id to metadata if applicable for multi-tenant RAG
        # e.g., if user: UserTable = Depends(current_active_user) is added:
        # metadata["user_id"] = str(user.id)

        dp_instance.ingest(document_id=file.filename, text=text, metadata=metadata)

        return JSONResponse(
            content={"message": f"Document '{file.filename}' ingested into namespace '{namespace}' successfully."},
            status_code=status.HTTP_201_CREATED,
        )
    except HTTPException as e:  # Re-raise HTTPExceptions
        raise e
    except Exception as e:
        logging.exception(f"Error ingesting document '{file.filename}' into namespace '{namespace}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ingest document: {str(e)}",
        )


@router.get("/query/")
async def query_rag(
    query: str,
    namespace: Optional[str] = None,  # Allow querying specific or all (if None)
    orchestrator: RagOrchestrator = Depends(get_orchestrator),
):
    """
    Queries the RAG system. If a namespace is provided, it attempts to query
    that specific namespace (though current combined retriever queries all).
    """
    try:
        # The current _get_combined_retriever queries all namespaces.
        # If specific namespace querying is needed, the retriever logic would need adjustment.
        retriever = orchestrator._get_combined_retriever()
        documents: List[Document] = await retriever.aget_relevant_documents(query)

        results = [
            {
                "page_content": doc.page_content,
                "metadata": doc.metadata,
            }
            for doc in documents
        ]
        return {"query": query, "namespace_queried": namespace or "all", "results": results}
    except Exception as e:
        logging.exception(f"Error querying RAG with query '{query}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query RAG: {str(e)}",
        )


# Placeholder for summarizing a session - could be expanded
@router.post("/session/{session_id}/summarize")
async def finalize_session(session_id: str, orchestrator: RagOrchestrator = Depends(get_orchestrator)):
    """
    Placeholder to trigger summarization of a session.
    In a real app, this might fetch all chat messages for the session,
    concatenate them, and then pass to the summarization chain.
    """
    try:
        summary = await orchestrator.summarize_session(session_id)
        return {"session_id": session_id, "summary": summary}
    except Exception as e:
        logging.exception(f"Error summarizing session {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to summarize session: {str(e)}",
        )
