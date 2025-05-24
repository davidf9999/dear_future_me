# scripts/ingest_rag_demo_data.py
import logging
import os
import re
import sys
from pathlib import Path
from typing import Dict, Set
from dotenv import load_dotenv

from app.core.settings import get_settings


# Load environment variables from .env and .env.dev
project_root = Path(__file__).parent.parent
load_dotenv(project_root / '.env')  # Load .env first
load_dotenv(project_root / '.env.dev', override=True)  # Then override with .env.dev

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_demo_data_dir(project_root: Path) -> Path:
    """Get the path to the demo data directory."""
    return project_root / "RAG_demo_data"

def extract_namespace_from_filename(filename: str) -> str:
    """
    Convert filename to expected namespace format.
    Example: "theory.txt" -> "dfm_theory"
    """
    # Remove .txt extension and convert to lowercase
    base_name = filename.lower().replace('.txt', '')
    # Convert to snake_case if not already
    base_name = re.sub(r'[^a-z0-9]+', '_', base_name).strip('_')
    # Add dfm_ prefix
    return f"dfm_{base_name}"

def get_expected_namespaces(settings) -> Dict[str, str]:
    """Get all RAG namespace settings that start with CHROMA_NAMESPACE_"""
    namespaces = {}
    for attr in dir(settings):
        if attr.startswith('CHROMA_NAMESPACE_'):
            namespace_value = getattr(settings, attr)
            namespaces[namespace_value] = attr
    return namespaces

def validate_mapping(files: Set[str], namespaces: Dict[str, str]) -> Dict[str, str]:
    """Validate and create file to namespace mapping."""
    mapping = {}
    errors = []
    
    for filename in files:
        expected_namespace = extract_namespace_from_filename(filename)
        
        if expected_namespace not in namespaces:
            errors.append(
                f"File '{filename}' would map to namespace '{expected_namespace}' "
                f"but no matching namespace found in settings"
            )
            continue
            
        mapping[filename] = expected_namespace
    
    if errors:
        logger.error("Namespace validation failed. Please fix the following issues:")
        for error in errors:
            logger.error(f"  - {error}")
        logger.error("\nAvailable namespaces in settings:")
        for ns, attr in namespaces.items():
            logger.error(f"  - {attr}: {ns}")
        sys.exit(1)
    
    return mapping

def main():
    # Get project root
    project_root = Path(__file__).parent.parent
    demo_data_dir = get_demo_data_dir(project_root)
    
    if not demo_data_dir.exists():
        logger.error(f"Demo data directory not found: {demo_data_dir}")
        return
    
    # Get all .txt files in the demo data directory
    txt_files = {f.name for f in demo_data_dir.glob('*.txt') if f.is_file()}
    if not txt_files:
        logger.error(f"No .txt files found in {demo_data_dir}")
        return
    
    # Initialize settings and get expected namespaces
    settings = get_settings()
    expected_namespaces = get_expected_namespaces(settings)
    
    # Validate and create mapping
    file_to_namespace = validate_mapping(txt_files, expected_namespaces)
    
    logger.info("File to namespace mapping:")
    for file, namespace in file_to_namespace.items():
        logger.info(f"  {file} -> {namespace}")
    
    # Import the ingestion function
    from scripts.ingest_rag_documents import ingest_file_to_namespace
    
    # Process each file
    for file_name, namespace in file_to_namespace.items():
        file_path = demo_data_dir / file_name
        logger.info(f"\nIngesting {file_name} into namespace: {namespace}")
        try:
            # Use the file name without extension as the document ID
            doc_id = file_name.rsplit('.', 1)[0]
            ingest_file_to_namespace(namespace, str(file_path), doc_id)
            logger.info(f"Successfully ingested {file_name}")
        except Exception as e:
            logger.error(f"Failed to ingest {file_name}: {str(e)}", exc_info=True)
            sys.exit(1)

if __name__ == "__main__":
    main()