# /home/dfront/code/dear_future_me/cli.py
# Full file content
import logging

import typer
from typing_extensions import Annotated

from app.core.settings import get_settings

# Import the specific ingestion function
from scripts.ingest_rag_documents import (
    ingest_file_to_namespace,
    ingest_text_to_namespace,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = typer.Typer(help="Dear Future Me CLI application.")
settings = get_settings()


@app.command(name="ingest_rag_file")
def ingest_rag_file_command(
    namespace: Annotated[str, typer.Option(help="ChromaDB namespace to ingest into.")],
    file_path: Annotated[str, typer.Option(help="Path to the text file to ingest.")],
    doc_id: Annotated[str, typer.Option(help="Optional document ID. If not provided, filename will be used.")] = None,
):
    """
    Ingests a text file into the specified RAG namespace.
    """
    if not doc_id:
        doc_id = file_path.split("/")[-1]  # Basic way to get filename as doc_id

    logger.info(f"Attempting to ingest file '{file_path}' with doc_id '{doc_id}' into namespace '{namespace}'...")
    try:
        ingest_file_to_namespace(namespace=namespace, file_path=file_path, doc_id=doc_id)
        typer.echo(f"Successfully ingested file '{file_path}' (doc_id: {doc_id}) into namespace '{namespace}'.")
    except FileNotFoundError:
        typer.echo(f"Error: File not found at '{file_path}'.", err=True)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"An error occurred during ingestion: {e}", err=True)
        logger.error(f"Ingestion failed for file '{file_path}': {e}", exc_info=True)
        raise typer.Exit(code=1)


@app.command(name="ingest_rag_text")
def ingest_rag_text_command(
    namespace: Annotated[str, typer.Option(help="ChromaDB namespace to ingest into.")],
    text_content: Annotated[str, typer.Option(help="Text content to ingest.", prompt=True)],
    doc_id: Annotated[str, typer.Option(help="Document ID for the text content.")],
):
    """
    Ingests raw text content into the specified RAG namespace.
    """
    logger.info(f"Attempting to ingest text with doc_id '{doc_id}' into namespace '{namespace}'...")
    try:
        ingest_text_to_namespace(namespace=namespace, text_content=text_content, doc_id=doc_id)
        typer.echo(f"Successfully ingested text (doc_id: {doc_id}) into namespace '{namespace}'.")
    except Exception as e:
        typer.echo(f"An error occurred during ingestion: {e}", err=True)
        logger.error(f"Ingestion failed for text doc_id '{doc_id}': {e}", exc_info=True)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
