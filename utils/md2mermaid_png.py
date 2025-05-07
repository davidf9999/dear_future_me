#!/usr/bin/env python3
import asyncio
import sys
import tempfile
from pathlib import Path

from pyppeteer import launch

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
  <style>
    body {{ margin: 0; padding: 0; }}
    .mermaid {{ width: 100%; height: 100%; }}
  </style>
  <script>
    mermaid.initialize({{ startOnLoad: true }});
  </script>
</head>
<body>
<div class="mermaid">
{diagram}
</div>
</body>
</html>
"""


async def render_to_png(html_path: str, output_png: str):
    browser = await launch({"args": ["--no-sandbox"]})
    page = await browser.newPage()
    await page.goto(f"file://{html_path}")
    # Wait until the <svg> is injected by mermaid
    await page.waitForSelector("svg")
    # Get the bounding box of the SVG element
    element = await page.querySelector("svg")
    box = await element.boundingBox()
    # Screenshot just that element
    await element.screenshot(
        {
            "path": output_png,
            "clip": {
                "x": box["x"],
                "y": box["y"],
                "width": box["width"],
                "height": box["height"],
            },
        }
    )
    await browser.close()


def extract_mermaid(md_text: str) -> str:
    """Grab the first ```mermaid``` fenced block."""
    in_block = False
    lines = []
    for line in md_text.splitlines():
        if line.strip().startswith("```mermaid"):
            in_block = True
            continue
        if in_block and line.strip().startswith("```"):
            break
        if in_block:
            lines.append(line)
    if not lines:
        raise ValueError("No mermaid block found in input markdown.")
    return "\n".join(lines)


def main():
    if len(sys.argv) not in (2, 3):
        print("Usage: python md2mermaid_png.py input.md [output.png]")
        sys.exit(1)

    md_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2] if len(sys.argv) == 3 else md_path.with_suffix(".png"))

    md_text = md_path.read_text(encoding="utf-8")
    diagram_code = extract_mermaid(md_text)

    # Write out a temporary HTML file
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
        html_content = HTML_TEMPLATE.format(diagram=diagram_code)
        f.write(html_content)
        html_file = f.name

    # Render to PNG
    asyncio.get_event_loop().run_until_complete(render_to_png(html_file, str(out_path)))

    print(f"Diagram rendered to {out_path}")


if __name__ == "__main__":
    main()
