# app/api/rag.py

from fastapi import APIRouter, Depends, UploadFile, Form, HTTPException, status
from app.api.orchestrator import RagOrchestrator, get_orchestrator
from app.rag.processor import DocumentProcessor

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post(
    "/ingest/",
    status_code=status.HTTP_200_OK,
    response_model=dict,
)
async def ingest_document(
    namespace: str = Form(..., pattern="^(theory|personal_plan|session_data)$"),
    doc_id: str = Form(...),
    text: str = Form(None),
    file: UploadFile = None,
):
    """
    Ingest raw text or an uploaded file into the specified namespace.
    """
    if file:
        raw = (await file.read()).decode("utf-8")
    elif text:
        raw = text
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either `text` or `file`",
        )

    proc = DocumentProcessor(namespace)
    proc.ingest(doc_id, raw, metadata={"namespace": namespace})
    return {"status": "ok", "namespace": namespace, "doc_id": doc_id}


@router.post(
    "/session/{session_id}/summarize",
    status_code=status.HTTP_200_OK,
    response_model=dict,
)
async def finalize_session(
    session_id: str,
    orchestrator: RagOrchestrator = Depends(get_orchestrator),
):
    """
    Summarize all `session_data` chunks for `session_id`,
    index the summary back into session_data, and return it.
    """
    summary = await orchestrator.summarize_session(session_id)
    return {"session_id": session_id, "summary": summary}
