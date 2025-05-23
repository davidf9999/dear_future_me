# /home/dfront/code/dear_future_me/app/api/rag.py
# Full file content
import logging  # Added for logging
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from pydantic import BaseModel  # For response model

from app.api.orchestrator import (  # Changed RagOrchestrator to Orchestrator
    Orchestrator,
    get_orchestrator,
)
from app.core.settings import get_settings  # To access namespace constants
from app.rag.processor import DocumentProcessor

router = APIRouter(tags=["rag"])  # Prefix /rag is applied in main.py
settings = get_settings()


# Define a more specific response model for ingestion
class IngestResponse(BaseModel):
    status: str
    namespace: str
    doc_id: str
    message: Optional[str] = None


@router.post(
    "/ingest/",
    status_code=status.HTTP_200_OK,
    response_model=IngestResponse,
)
async def ingest_document(
    namespace: str = Form(
        ...,
        pattern=(
            f"^({settings.CHROMA_NAMESPACE_THEORY}|"
            f"{settings.CHROMA_NAMESPACE_PERSONAL_PLAN}|"
            f"{settings.CHROMA_NAMESPACE_SESSION_DATA}|"
            f"{settings.CHROMA_NAMESPACE_FUTURE_ME}|"
            f"{settings.CHROMA_NAMESPACE_THERAPIST_NOTES}|"
            f"{settings.CHROMA_NAMESPACE_DFM_CHAT_HISTORY_SUMMARIES})$"
        ),
    ),
    doc_id: str = Form(...),
    text: Optional[str] = Form(None),
    file: Optional[UploadFile] = None,
    session_id: Optional[str] = Form(None),  # Added session_id
):
    if not text and not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either `text` or `file`",
        )

    raw_content: str
    if file:
        try:
            contents = await file.read()
            raw_content = contents.decode("utf-8")
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Error processing uploaded file: {e}",
            )
        finally:
            await file.close()
    elif text:
        raw_content = text
    else:  # Should not be reached due to the check above, but as a safeguard
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No content provided.")

    try:
        proc = DocumentProcessor(namespace=namespace)

        # Prepare metadata
        doc_metadata = {"namespace": namespace, "original_doc_id": doc_id}
        if namespace == settings.CHROMA_NAMESPACE_SESSION_DATA and session_id:
            doc_metadata["session_id"] = session_id
            logging.info(f"Ingesting into '{namespace}' with session_id: '{session_id}' for doc_id: '{doc_id}'")
        elif namespace == settings.CHROMA_NAMESPACE_SESSION_DATA and not session_id:
            logging.warning(
                f"Ingesting into '{namespace}' (session_data) but no session_id provided for doc_id: '{doc_id}'. "
                "Summarization for this session might not work correctly."
            )

        proc.ingest(doc_id, raw_content, metadata=doc_metadata)

        return IngestResponse(
            status="ok", namespace=namespace, doc_id=doc_id, message="Document ingested successfully."
        )
    except Exception as e:
        logging.exception(f"Error during ingestion for namespace {namespace}, doc_id {doc_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ingest document: {e}",
        )


class SummarizeResponse(BaseModel):
    session_id: str
    summary: Optional[str]  # Summary can be None if no docs
    documents_processed: int


@router.post(
    "/session/{session_id}/summarize",
    status_code=status.HTTP_200_OK,
    response_model=SummarizeResponse,
    # Added user_id as a required query parameter for summarization
)
async def finalize_session(
    session_id: str,
    user_id: str,  # Make user_id explicit for summarization
    orchestrator: Orchestrator = Depends(get_orchestrator),  # Correctly typed
):
    try:
        # Orchestrator.summarize_session now returns a tuple (summary, count)
        summary, count = await orchestrator.summarize_session(session_id=session_id, user_id=user_id)
        return SummarizeResponse(session_id=session_id, summary=summary, documents_processed=count)
    except Exception as e:
        logging.exception(f"Error summarizing session {session_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to summarize session: {e}",
        )
