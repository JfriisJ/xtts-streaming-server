from fastapi import FastAPI, UploadFile, HTTPException
import os
import subprocess
import logging
import zipfile
from xml.etree.ElementTree import parse
import re

# Setup logging
os.makedirs('/app/logs', exist_ok=True)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("/app/logs/converter.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="File Conversion API",
    description="Converts files to ODT and extracts structured text as JSON",
    version="0.0.1",
    docs_url="/",
)

UPLOAD_FOLDER = "/app/uploads"
OUTPUT_FOLDER = "/app/outputs"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Markdown to JSON Parser

def parse_markdown_to_json(markdown_content, remove_code_blocks=True, remove_tables=True):
    """
    Parse Markdown content into structured JSON with hierarchical levels.
    - Removes Markdown formatting like `**`.
    - Optionally removes code blocks and tables.
    """
    def clean_text(text):
        """Removes Markdown formatting (e.g., `**`) from the text."""
        return re.sub(r"\*\*(.*?)\*\*", r"\1", text).strip()

    def is_table_line(line):
        """
        Checks if a line is part of a Markdown table.
        A table line contains `|` and may also have `---` to define headers.
        """
        return "|" in line and not line.strip().startswith("```")

    lines = markdown_content.strip().split("\n")
    if not lines:
        return {"Title": "", "Sections": []}

    title = clean_text(lines[0].strip("# ").strip())
    json_data = {"Title": title, "Sections": []}
    current_section = None
    current_subsection = None
    in_code_block = False
    in_table = False
    code_block_lines = []

    for line in lines[1:]:
        stripped_line = line.strip()

        # Handle code blocks
        if stripped_line.startswith("```"):  # Toggle code block mode
            in_code_block = not in_code_block
            if not in_code_block:  # Closing a code block
                if not remove_code_blocks:
                    code_content = "\n".join(code_block_lines).strip()
                    if current_subsection:
                        current_subsection["Content"] += f"\n\n{code_content}" if current_subsection["Content"] else code_content
                    elif current_section:
                        current_section["Content"] += f"\n\n{code_content}" if current_section["Content"] else code_content
                code_block_lines = []
            continue

        if in_code_block:
            if not remove_code_blocks:
                code_block_lines.append(line)
            continue

        # Handle tables
        if remove_tables:
            if is_table_line(stripped_line):
                in_table = True
                continue
            elif in_table and not stripped_line:  # End of table
                in_table = False
                continue

        # Skip empty lines and horizontal rules
        if not stripped_line or stripped_line == "---":
            continue

        # Handle `#` as top-level sections
        if stripped_line.startswith("# "):
            if current_section:
                if current_subsection:
                    current_section["Subsections"].append(current_subsection)
                    current_subsection = None
                json_data["Sections"].append(current_section)
            current_section = {"Heading": clean_text(stripped_line[2:].strip()), "Content": "", "Subsections": []}

        # Handle `##` as mid-level sections
        elif stripped_line.startswith("## "):
            if current_subsection:
                current_section["Subsections"].append(current_subsection)
            current_subsection = {"Heading": clean_text(stripped_line[3:].strip()), "Content": "", "Subsections": []}

        # Handle `###` as lowest-level sections
        elif stripped_line.startswith("### "):
            if current_subsection:
                current_subsection["Subsections"].append({
                    "Heading": clean_text(stripped_line[4:].strip()),
                    "Content": []
                })

        # Add content to the current section or subsection
        else:
            cleaned_line = clean_text(stripped_line)
            if current_subsection and current_subsection["Subsections"]:
                current_subsection["Subsections"][-1]["Content"].append(cleaned_line)
            elif current_subsection:
                current_subsection["Content"] += f"\n{cleaned_line}" if current_subsection["Content"] else cleaned_line
            elif current_section:
                current_section["Content"] += f"\n{cleaned_line}" if current_section["Content"] else cleaned_line

    # Append the last subsection and section
    if current_subsection:
        current_section["Subsections"].append(current_subsection)
    if current_section:
        json_data["Sections"].append(current_section)

    return json_data


# Extract text from ODT
def parse_odt_to_json(odt_file_path):
    """Extracts and organizes text from an ODT file into JSON."""
    try:
        with zipfile.ZipFile(odt_file_path, 'r') as odt_zip:
            with odt_zip.open('content.xml') as content_file:
                tree = parse(content_file)
                root = tree.getroot()

        namespaces = {'text': 'urn:oasis:names:tc:opendocument:xmlns:text:1.0'}
        styled_content = {
            "Title": [],
            "Heading 1": [],
            "Heading 2": [],
            "Heading 3": [],
            "Heading 4": [],
            "Heading 5": [],
            "Paragraphs": []
        }

        for paragraph in root.findall('.//text:p', namespaces):
            style_name = paragraph.attrib.get(f'{{{namespaces["text"]}}}style-name', "Default")
            text_content = paragraph.text or ""
            text_content = text_content.strip()

            if not text_content:
                continue

            if style_name.startswith("Title"):
                styled_content["Title"].append(text_content)
            elif style_name.startswith("Heading_20_1"):
                styled_content["Heading 1"].append(text_content)
            elif style_name.startswith("Heading_20_2"):
                styled_content["Heading 2"].append(text_content)
            elif style_name.startswith("Heading_20_3"):
                styled_content["Heading 3"].append(text_content)
            elif style_name.startswith("Heading_20_4"):
                styled_content["Heading 4"].append(text_content)
            elif style_name.startswith("Heading_20_5"):
                styled_content["Heading 5"].append(text_content)
            else:
                styled_content["Paragraphs"].append(text_content)

        return {k: v for k, v in styled_content.items() if v}
    except Exception as e:
        logger.error(f"Error extracting text from ODT file: {e}")
        raise HTTPException(status_code=500, detail="Error extracting text from ODT file.")

@app.post("/convert")
async def convert(file: UploadFile):
    input_path = os.path.join(UPLOAD_FOLDER, file.filename)
    output_path = os.path.join(OUTPUT_FOLDER, f"{os.path.splitext(file.filename)[0]}.odt")

    try:
        with open(input_path, "wb") as f:
            f.write(await file.read())

        # Handle Markdown files directly
        if file.filename.endswith(".md"):
            with open(input_path, "r", encoding="utf-8") as md_file:
                markdown_content = md_file.read()
            json_output = parse_markdown_to_json(markdown_content)
            return {"message": "Conversion successful", "json_output": json_output}

        # Handle other formats to ODT and parse
        convert_to_odt(input_path, output_path, file.filename)
        json_output = parse_odt_to_json(output_path)
        return {"message": "Conversion successful", "json_output": json_output}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {e}")
    finally:
        if os.path.exists(input_path):
            os.remove(input_path)


def convert_to_odt(input_path, output_path, filename):
    """Converts various file formats to ODT."""
    try:
        if filename.endswith(".md"):
            subprocess.run(["pandoc", input_path, "-f", "markdown", "-t", "odt", "-o", output_path], check=True)
        elif filename.endswith(".epub"):
            subprocess.run(["pandoc", input_path, "-f", "epub", "-t", "odt", "-o", output_path], check=True)
        elif filename.endswith(".html"):
            subprocess.run(["pandoc", input_path, "-f", "html", "-t", "odt", "-o", output_path], check=True)
        elif filename.endswith(".docx"):
            subprocess.run(["libreoffice", "--headless", "--convert-to", "odt", "--outdir", os.path.dirname(output_path), input_path], check=True)
        elif filename.endswith(".txt"):
            subprocess.run(["pandoc", input_path, "-f", "plain", "-t", "odt", "-o", output_path], check=True)
        elif filename.endswith(".pdf"):
            intermediate_html = os.path.splitext(output_path)[0] + ".html"
            subprocess.run(["pdftohtml", "-s", input_path, intermediate_html], check=True)
            subprocess.run(["pandoc", intermediate_html, "-f", "html", "-t", "odt", "-o", output_path], check=True)
            os.remove(intermediate_html)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type")
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Conversion failed for {filename}: {e}")

@app.get("/health")
def health():
    try:
        # Add any specific service checks here
        return {"status": "healthy"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
