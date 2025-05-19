# /home/dfront/code/dear_future_me/app/api/rag.py
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from pydantic import BaseModel  # For response model

from app.api.orchestrator import RagOrchestrator, get_orchestrator
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
    response_model=IngestResponse,  # Use the new response model
)
async def ingest_document(
    namespace: str = Form(
        ...,
        # Updated pattern to match new namespaces from settings
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
    text: Optional[str] = Form(None),  # Made Optional
    file: Optional[UploadFile] = None,  # Kept as Optional
    # orchestrator: RagOrchestrator = Depends(get_orchestrator) # Orchestrator not directly needed for ingest here
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
        proc = DocumentProcessor(namespace=namespace)  # Uses settings for Chroma client
        proc.ingest(doc_id, raw_content, metadata={"namespace": namespace, "original_doc_id": doc_id})
        return IngestResponse(
            status="ok", namespace=namespace, doc_id=doc_id, message="Document ingested successfully."
        )
    except Exception as e:
        # Log the exception for server-side debugging
        # import logging
        # logging.exception(f"Error during ingestion for namespace {namespace}, doc_id {doc_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ingest document: {e}",
        )


class SummarizeResponse(BaseModel):
    session_id: str
    summary: str


@router.post(
    "/session/{session_id}/summarize",
    status_code=status.HTTP_200_OK,
    response_model=SummarizeResponse,  # Use a specific response model
)
async def finalize_session(
    session_id: str,
    orchestrator: RagOrchestrator = Depends(get_orchestrator),
):
    try:
        summary = await orchestrator.summarize_session(session_id)
        return SummarizeResponse(session_id=session_id, summary=summary)
    except Exception as e:
        # import logging
        # logging.exception(f"Error summarizing session {session_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to summarize session: {e}",
        )
