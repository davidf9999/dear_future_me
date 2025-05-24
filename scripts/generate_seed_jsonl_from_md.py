# /home/dfront/code/dear_future_me/scripts/generate_seed_jsonl_from_md.py
# Full file content
import json
import re # For regular expression matching of separator
from pathlib import Path


def parse_markdown_table(md_content: str) -> dict:
    """
    Parses a Markdown table and extracts data from the 'name' and
    'example content...' columns.

    Args:
        md_content: A string containing the Markdown table.

    Returns:
        A dictionary where keys are from the 'name' column and
        values are from the 'example content...' column.
    """
    data = {}
    lines = md_content.strip().split('\n')

    header_line_index = -1
    # Find the actual header line (should contain '|')
    for i, line in enumerate(lines):
        if '|' in line and not line.strip().startswith('|--'): # Basic check to avoid separator as header
            # Further check: a header shouldn't ONLY contain '-' or ':' between pipes
            # This is a heuristic to distinguish from a separator line
            cells_for_header_check = [cell.strip() for cell in line.split('|')]
            if not all(re.match(r"^:?-+:?$", cell) for cell in cells_for_header_check if cell): # Check non-empty cells
                header_line_index = i
                break
    
    if header_line_index == -1:
        print("Error: Could not find a valid table header row (e.g., | col1 | col2 |).")
        return data

    header_line = lines[header_line_index]
    print(f"Identified header line: '{header_line}'")

    # Use the raw split for indexing, but a cleaned version for matching
    raw_headers = [h.strip() for h in header_line.split('|')]
    # Cleaned headers for matching (lowercase, no extra spaces)
    cleaned_headers_for_matching = [h.lower().strip() for h in raw_headers if h.strip()]
    
    # Find the index of the 'name' column and the 'example content' column
    try:
        # Find index in raw_headers based on cleaned_headers_for_matching
        name_keyword = 'name'
        # Find the cleaned header that IS 'name'
        cleaned_name_header_index = next(i for i, h_cleaned in enumerate(cleaned_headers_for_matching) if name_keyword == h_cleaned)
        # Find the original raw header that corresponds to this cleaned header
        name_col_original_header = next(h_raw for h_raw in raw_headers if h_raw.lower().strip() == cleaned_headers_for_matching[cleaned_name_header_index])
        name_col_index = raw_headers.index(name_col_original_header)


        # The "example content" column header is long, match by a significant substring
        example_keyword_1 = 'example content'
        example_keyword_2 = 'hypothetical user'
        cleaned_example_header_index = next(i for i, h_cleaned in enumerate(cleaned_headers_for_matching) if example_keyword_1 in h_cleaned and example_keyword_2 in h_cleaned)
        example_col_original_header = next(h_raw for h_raw in raw_headers if example_keyword_1 in h_raw.lower() and example_keyword_2 in h_raw.lower())
        example_col_index = raw_headers.index(example_col_original_header)


    except StopIteration:
        print("Error: Could not find 'name' or 'example content' columns in the table header.")
        print(f"Raw detected headers: {raw_headers}")
        print(f"Cleaned headers for matching: {cleaned_headers_for_matching}")
        return data

    # Ensure there's a separator line after the header.
    separator_line_candidate = lines[header_line_index + 1].strip()
    # Regex to match a typical markdown table separator row.
    # Allows for optional colons for alignment and requires at least one dash per segment.
    # Examples: |:---|---|:--:| , | --- | ---- |
    # The regex looks for patterns like |:---|, |---|, or |---:| separated by |
    is_separator_regex = re.compile(r"^\s*\|(?:\s*:?-+:?\s*\|)+$")

    if header_line_index + 1 >= len(lines) or not is_separator_regex.match(separator_line_candidate):
        print(f"Error: Table separator line (e.g., |---|---|) not found or not matched by regex after the header.")
        if header_line_index + 1 < len(lines):
            print(f"Line after header: '{lines[header_line_index + 1]}'")
            print(f"Candidate for separator (stripped): '{separator_line_candidate}'")
        return data

    # Start processing data rows from after the separator line
    for line in lines[header_line_index + 2:]:
        if not line.strip() or line.startswith('|--'): # Skip empty lines or separator
            continue
        
        cells = [cell.strip() for cell in line.split('|')]

        # Ensure cells list is long enough before trying to access indices
        if len(cells) > name_col_index and len(cells) > example_col_index:
            key = cells[name_col_index].replace('\\_', '_')
            value = cells[example_col_index] 
        else:
            print(f"Skipping malformed row (not enough cells): '{line}'")
            continue
            # Skip user_id as it's handled by the main seeder
        if key == "user_id":
            continue
        # Clean up common markdown artifacts like escaped newlines
        # if key == "dfm_use_integration_status":
        #     value = value.strip('`')
        value = value.replace('', '\n').replace('\n', '\n')
        if value: # Only add if there's content
            data[key] = value
    return data


def main():
    scripts_dir = Path(__file__).parent
    base_dir = scripts_dir.parent
    data_dir = base_dir / "data"
    rdb_demo_data_dir = base_dir / "RDB_demo_data"

    user_profile_md_path = rdb_demo_data_dir / "UserProfileTable.md"
    safety_plan_md_path = rdb_demo_data_dir / "SafetyPlanTable.md"
    output_jsonl_path = data_dir / "seed_users.jsonl"

    if not user_profile_md_path.exists():
        print(f"Error: UserProfileTable.md not found at {user_profile_md_path}")
        return
    if not safety_plan_md_path.exists():
        print(f"Error: SafetyPlanTable.md not found at {safety_plan_md_path}")
        return

    # Create data directory if it doesn't exist
    data_dir.mkdir(parents=True, exist_ok=True)

    with open(user_profile_md_path, 'r', encoding='utf-8') as f:
        user_profile_md = f.read()
    profile_data = parse_markdown_table(user_profile_md)

    with open(safety_plan_md_path, 'r', encoding='utf-8') as f:
        safety_plan_md = f.read()
    safety_plan_data = parse_markdown_table(safety_plan_md)

    # Construct the user object for JSONL
    # Using "Idan" as the example user based on the content
    user_seed_entry = {
        "email": "idan.seed@example.com",
        "first_name": "Idan",
        "last_name": "SeedUser", # Placeholder last name
        "hashed_password": "seeded_placeholder_hash", # Placeholder, will be handled by User Manager if integrated
        "is_active": True,
        "is_verified": True,
        "is_superuser": False,
        "profile": profile_data,
        "safety_plan": safety_plan_data
    }

    # Write to JSONL file
    with open(output_jsonl_path, 'w', encoding='utf-8') as f:
        json.dump(user_seed_entry, f)
        f.write('\n') # JSONL means one JSON object per line

    print(f"Successfully generated seed data at: {output_jsonl_path}")
    print("JSONL content for Idan:")
    print(json.dumps(user_seed_entry, indent=2))


if __name__ == "__main__":
    main()
