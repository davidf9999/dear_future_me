# scripts/ingest_rag_documents.py
# Full file content
import logging
import os

from app.core.settings import get_settings
from app.rag.processor import DocumentProcessor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()


def ingest_file_to_namespace(namespace: str, file_path: str, doc_id: str):
    """
    Ingests content from a text file into the specified ChromaDB namespace.

    Args:
        namespace: The ChromaDB namespace (collection name).
        file_path: Path to the text file.
        doc_id: The ID for the document.
    """
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        text_content = f.read()

    ingest_text_to_namespace(namespace, text_content, doc_id)


def ingest_text_to_namespace(namespace: str, text_content: str, doc_id: str):
    """
    Ingests raw text content into the specified ChromaDB namespace.

    Args:
        namespace: The ChromaDB namespace (collection name).
        text_content: The text content to ingest.
        doc_id: The ID for the document.
    """
    logger.info(f"Initializing DocumentProcessor for namespace: {namespace}")

    # Determine if we are using remote Chroma or local based on settings
    # This logic mirrors DocumentProcessor's internal decision
    use_remote_chroma = bool(settings.CHROMA_HOST and settings.CHROMA_PORT)

    if use_remote_chroma:
        processor = DocumentProcessor(
            namespace=namespace,
            chroma_host=settings.CHROMA_HOST,
            chroma_port=settings.CHROMA_PORT,
        )
        logger.info(f"Using remote Chroma server for ingestion: {settings.CHROMA_HOST}:{settings.CHROMA_PORT}")
    else:
        processor = DocumentProcessor(namespace=namespace, persist_directory=settings.CHROMA_PERSIST_DIR)
        logger.info(f"Using local persistent Chroma for ingestion at: {settings.CHROMA_PERSIST_DIR}")

    logger.info(f"Ingesting document ID '{doc_id}' into namespace '{namespace}'.")
    try:
        processor.ingest(doc_id=doc_id, text=text_content)
        # If using local Chroma and explicit persistence is desired (though often automatic)
        if not use_remote_chroma:
            processor.persist()  # Chroma client handles persistence, but calling it ensures it if needed.
        logger.info(f"Successfully ingested document ID '{doc_id}'.")
    except Exception as e:
        logger.error(f"Error during ingestion of document ID '{doc_id}': {e}", exc_info=True)
        raise


if __name__ == "__main__":
    # Example usage (for direct script execution testing)
    # Ensure your .env file is configured or settings are available
    # For local Chroma, CHROMA_HOST and CHROMA_PORT should be unset or None in .env
    # For remote Chroma, CHROMA_HOST and CHROMA_PORT should be set.

    example_namespace = settings.CHROMA_NAMESPACE_THEORY  # or any other test namespace
    example_doc_id = "cli_test_doc_001"
    example_text = "This is a test document ingested via the CLI script."

    # To test file ingestion:
    # test_file_path = "path/to/your/testfile.txt"
    # with open(test_file_path, "w") as f:
    #     f.write("Content for the test file.")
    # try:
    #     print(f"Testing file ingestion into namespace: {example_namespace}")
    #     ingest_file_to_namespace(example_namespace, test_file_path, "cli_test_file_doc_001")
    #     print("File ingestion test successful.")
    # except Exception as e:
    #     print(f"File ingestion test failed: {e}")

    # To test text ingestion:
    try:
        print(f"\nTesting text ingestion into namespace: {example_namespace}")
        ingest_text_to_namespace(example_namespace, example_text, example_doc_id)
        print("Text ingestion test successful.")
    except Exception as e:
        print(f"Text ingestion test failed: {e}")
