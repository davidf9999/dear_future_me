# scripts/ingest_rag_documents.py
import asyncio
from pathlib import Path

import httpx

# Assuming your FastAPI app runs on localhost:8000
BASE_API_URL = "http://localhost:8000"
# Define your RAG source directory and how to map files to namespaces
RAG_SOURCE_DIR = Path(__file__).parent.parent / "rag_sources"  # Example path
# Example: files in RAG_SOURCE_DIR/theory go to settings.CHROMA_NAMESPACE_THEORY
# You'll need to import your settings to get the actual namespace values
# from app.core.settings import get_settings
# settings = get_settings()


async def ingest_single_document(client: httpx.AsyncClient, namespace: str, doc_id: str, file_path: Path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # The API expects form data
        data = {
            "namespace": namespace,
            "doc_id": doc_id,
            # "text": content # Use 'text' if sending directly
        }
        files = {"file": (file_path.name, open(file_path, "rb"), "text/markdown")}  # Or appropriate content type

        # response = await client.post(f"{BASE_API_URL}/rag/ingest/", data=data, files=files) # If sending as file
        response = await client.post(
            f"{BASE_API_URL}/rag/ingest/", data={**data, "text": content}
        )  # If sending as text

        if 200 <= response.status_code < 300:
            print(f"Successfully ingested {doc_id} into {namespace}: {response.json()}")
        else:
            print(
                f"Failed to ingest {doc_id} into {namespace}. Status: {response.status_code}, Response: {response.text}"
            )
    except Exception as e:
        print(f"Error ingesting {doc_id} from {file_path}: {e}")
    finally:
        # Close the file if opened with 'rb' for the files parameter
        if "files" in locals() and files["file"][1]:
            files["file"][1].close()


async def main():
    # This is a simplified example. You'd need more robust logic
    # to determine namespace and doc_id from file paths/names.
    # For example, map subdirectories to namespaces.

    # Example: Ingest all .md files from a 'theory' subdirectory into the theory namespace
    # theory_namespace = settings.CHROMA_NAMESPACE_THEORY # Get from settings
    theory_namespace = "dfm_theory"  # Placeholder if settings not imported here
    theory_docs_path = RAG_SOURCE_DIR / "theory"

    async with httpx.AsyncClient() as client:
        if theory_docs_path.exists() and theory_docs_path.is_dir():
            for md_file in theory_docs_path.glob("*.md"):
                doc_id = md_file.stem  # Use filename without extension as doc_id
                await ingest_single_document(client, theory_namespace, doc_id, md_file)
        else:
            print(f"Directory not found: {theory_docs_path}")

        # Repeat for other namespaces and their source directories...


if __name__ == "__main__":
    # Make sure your FastAPI server is running before executing this script.
    asyncio.run(main())
