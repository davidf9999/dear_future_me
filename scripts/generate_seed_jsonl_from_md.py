# scripts/generate_seed_jsonl_from_md.py
import csv
import json
import sys
from pathlib import Path

# Determine the project root directory and add it to sys.path
# This allows the script to be run from any location and still find the 'app' module.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.settings import get_settings # noqa: E402, F401 pylint: disable=unused-import, wrong-import-position

# Get settings to access RAG namespace configurations
settings = get_settings()


def md_to_jsonl(md_file_path: Path, jsonl_file_path: Path, namespace: str):
    """
    Converts a Markdown file with a table into a JSONL file suitable for RAG ingestion.
    Each row in the table (excluding the header) becomes a JSON object in the JSONL file.
    The 'doc_id' is derived from a 'doc_id' column in the table.
    The 'text' for ingestion is constructed from all other columns in that row.
    """
    if not md_file_path.exists():
        print(f"Error: Markdown file not found at {md_file_path}")
        return

    with open(md_file_path, 'r', encoding='utf-8') as md_file, \
         open(jsonl_file_path, 'w', encoding='utf-8') as jsonl_file:

        # Read the Markdown table content
        # This assumes a simple pipe-table format. More complex parsing might be needed for other MD table types.
        lines = md_file.readlines()
        table_lines = [line.strip() for line in lines if line.strip().startswith('|') and line.strip().endswith('|')]

        if not table_lines or len(table_lines) < 2: # Need at least header and separator/data
            print(f"Error: No valid Markdown table found or table is too short in {md_file_path}")
            return

        # Parse header
        raw_headers = [header.strip() for header in table_lines[0].strip('|').split('|')]
        # Skip the separator line (table_lines[1])

        # Find the column index for 'doc_id'
        try:
            doc_id_col_index = next(i for i, h in enumerate(raw_headers) if h.lower() == 'doc_id')
        except StopIteration:
            print(f"Error: 'doc_id' column not found in the header of {md_file_path}")
            print(f"Available headers: {raw_headers}")
            return

        # Process data rows
        for line_index, line_content in enumerate(table_lines[2:], start=2): # Start from the first data row
            row_values = [cell.strip() for cell in line_content.strip('|').split('|')]
            if len(row_values) != len(raw_headers):
                print(f"Warning: Skipping row {line_index+1} in {md_file_path} due to mismatched column count. Expected {len(raw_headers)}, got {len(row_values)}.")
                continue

            doc_id = row_values[doc_id_col_index]
            if not doc_id:
                print(f"Warning: Skipping row {line_index+1} in {md_file_path} due to empty 'doc_id'.")
                continue

            # Construct text from other columns
            text_parts = []
            for i, cell_value in enumerate(row_values):
                if i != doc_id_col_index: # Exclude the doc_id column itself from the text
                    text_parts.append(f"{raw_headers[i]}: {cell_value}")
            ingestion_text = "\n".join(text_parts)

            record = {
                "namespace": namespace,
                "doc_id": doc_id,
                "text": ingestion_text
            }
            jsonl_file.write(json.dumps(record) + '\n')

    print(f"Successfully converted {md_file_path} to {jsonl_file_path} for namespace '{namespace}'")


def csv_to_jsonl(csv_file_path: Path, jsonl_file_path: Path, namespace: str):
    """
    Converts a CSV file into a JSONL file suitable for RAG ingestion.
    Each row in the CSV (excluding the header) becomes a JSON object in the JSONL file.
    The 'doc_id' is derived from a 'doc_id' column in the CSV.
    The 'text' for ingestion is constructed from all other columns in that row.
    """
    if not csv_file_path.exists():
        print(f"Error: CSV file not found at {csv_file_path}")
        return

    with open(csv_file_path, 'r', encoding='utf-8-sig') as csv_file, \
         open(jsonl_file_path, 'w', encoding='utf-8') as jsonl_file:

        reader = csv.reader(csv_file)
        try:
            raw_headers = next(reader) # Get header row
        except StopIteration:
            print(f"Error: CSV file {csv_file_path} is empty or has no header.")
            return

        # Find the column index for 'doc_id'
        try:
            doc_id_col_index = next(i for i, h in enumerate(raw_headers) if h.lower() == 'doc_id')
        except StopIteration:
            print(f"Error: 'doc_id' column not found in the header of {csv_file_path}")
            print(f"Available headers: {raw_headers}")
            return
        
        # Find the column index for the example content based on a keyword in its header
        example_keyword_1 = 'example content'
        example_keyword_2 = 'hypothetical user'
        # The variable cleaned_example_header_index was unused.
        # Assuming the goal was to find the index in raw_headers:
        try:
            example_col_index = next(i for i, h_raw in enumerate(raw_headers) if example_keyword_1 in h_raw.lower() and example_keyword_2 in h_raw.lower())
        except StopIteration:
            print(f"Warning: Example content column with keywords '{example_keyword_1}' and '{example_keyword_2}' not found in header of {csv_file_path}.")
            example_col_index = -1 # Or handle as an error if this column is critical


        for row_index, row in enumerate(reader):
            if len(row) != len(raw_headers):
                print(f"Warning: Skipping row {row_index+2} in {csv_file_path} due to mismatched column count. Expected {len(raw_headers)}, got {len(row)}.")
                continue

            doc_id = row[doc_id_col_index]
            if not doc_id:
                print(f"Warning: Skipping row {row_index+2} in {csv_file_path} due to empty 'doc_id'.")
                continue
            
            example_content = ""
            if example_col_index != -1: # Check if example column was found
                example_content = row[example_col_index]

            # Construct text from other columns, excluding doc_id and the example column itself
            text_parts = []
            for i, cell_value in enumerate(row):
                if i != doc_id_col_index and (example_col_index == -1 or i != example_col_index): # only skip example_col if it was found
                    text_parts.append(f"{raw_headers[i]}: {cell_value}")
            
            # Prepend the example content to the text parts if it exists
            if example_content:
                ingestion_text = f"Example Content for {doc_id}:\n{example_content}\n\nAdditional Info:\n" + "\n".join(text_parts)
            else:
                ingestion_text = "\n".join(text_parts)


            record = {
                "namespace": namespace,
                "doc_id": doc_id,
                "text": ingestion_text
            }
            jsonl_file.write(json.dumps(record) + '\n')

    print(f"Successfully converted {csv_file_path} to {jsonl_file_path} for namespace '{namespace}'")


if __name__ == "__main__":
    # Define mappings from source file to target namespace and output file
    # This script now expects source files to be in PROJECT_ROOT/RDB_demo_data/
    # and output JSONL files will be placed in PROJECT_ROOT/demo_data/<namespace_name>/
    source_data_dir = PROJECT_ROOT / "RDB_demo_data"
    output_base_dir = PROJECT_ROOT / "demo_data"

    # Ensure base output directory exists
    output_base_dir.mkdir(parents=True, exist_ok=True)

    # Define files and their target namespaces
    # Using settings for namespace names to ensure consistency
    files_to_process = [
        {"source_md": "UserProfileTable.md", "namespace": settings.CHROMA_NAMESPACE_FUTURE_ME, "output_jsonl": "future_me_profiles.jsonl"},
        {"source_md": "SafetyPlanTable.md", "namespace": settings.CHROMA_NAMESPACE_PERSONAL_PLAN, "output_jsonl": "personal_safety_plans.jsonl"},
        # Add more files here as needed, e.g., for theory if you have a UserProfileTable.md for it
        # {"source_md": "TheoryContent.md", "namespace": settings.CHROMA_NAMESPACE_THEORY, "output_jsonl": "theory_content.jsonl"},
        {"source_csv": "TheoryTable.csv", "namespace": settings.CHROMA_NAMESPACE_THEORY, "output_jsonl": "theory_content_from_csv.jsonl"},
    ]

    for item in files_to_process:
        namespace_dir = output_base_dir / item["namespace"]
        namespace_dir.mkdir(parents=True, exist_ok=True) # Ensure namespace-specific output directory exists
        
        output_jsonl_path = namespace_dir / item["output_jsonl"]

        if "source_md" in item:
            source_md_path = source_data_dir / item["source_md"]
            md_to_jsonl(source_md_path, output_jsonl_path, item["namespace"])
        elif "source_csv" in item:
            source_csv_path = source_data_dir / item["source_csv"]
            csv_to_jsonl(source_csv_path, output_jsonl_path, item["namespace"])


    print("JSONL generation process completed.")
