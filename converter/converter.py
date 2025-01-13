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

def parse_markdown_to_json(markdown_content):
    """
    Parse a Markdown string into a JSON structure based on heading levels.
    Handles headings, paragraphs, and code blocks, and removes unwanted elements.
    """
    lines = markdown_content.split("\n")
    json_data = {
        "Title": [],
        "Heading 1": [],
        "Heading 2": [],
        "Heading 3": [],
        "Heading 4": [],
        "Heading 5": [],
        "Code": []
    }
    current_section = None

    code_block_active = False  # To track whether we're inside a code block
    code_block_buffer = []

    for line in lines:
        stripped_line = line.strip()

        # Handle code blocks
        if stripped_line.startswith("```"):
            if not code_block_active:
                # Start of a code block
                code_block_active = True
                code_block_buffer = []
            else:
                # End of a code block
                code_block_active = False
                json_data["Code"].append("\n".join(code_block_buffer))
            continue

        if code_block_active:
            # Accumulate code block lines
            code_block_buffer.append(stripped_line)
            continue

        # Remove horizontal lines and empty lines
        if stripped_line == "---" or not stripped_line:
            continue

        # Normalize inline Markdown syntax
        stripped_line = re.sub(r"\*\*(.*?)\*\*", r"\1", stripped_line)  # Remove bold (**)
        stripped_line = re.sub(r"\*(.*?)\*", r"\1", stripped_line)  # Remove italics (*)

        # Categorize headings
        if stripped_line.startswith("# "):
            current_section = "Title"
            json_data["Title"].append(stripped_line[2:])
        elif stripped_line.startswith("## "):
            current_section = "Heading 1"
            json_data["Heading 1"].append(stripped_line[3:])
        elif stripped_line.startswith("### "):
            current_section = "Heading 2"
            json_data["Heading 2"].append(stripped_line[4:])
        elif stripped_line.startswith("#### "):
            current_section = "Heading 3"
            json_data["Heading 3"].append(stripped_line[5:])
        elif stripped_line.startswith("##### "):
            current_section = "Heading 4"
            json_data["Heading 4"].append(stripped_line[6:])
        elif stripped_line.startswith("###### "):
            current_section = "Heading 5"
            json_data["Heading 5"].append(stripped_line[7:])
        else:
            # Add remaining content to the current section
            if current_section:
                json_data[current_section].append(stripped_line)

    # Filter out empty categories
    return {k: v for k, v in json_data.items() if v}


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

        # Convert other formats to ODT
        convert_to_odt(input_path, output_path, file.filename)

        # Parse the ODT to JSON
        json_output = parse_odt_to_json(output_path)
        return {
            "message": "Conversion successful",
            "json_output": json_output
        }

    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Conversion failed: {e}")
    finally:
        if os.path.exists(input_path):
            os.remove(input_path)
        if os.path.exists(output_path):
            os.remove(output_path)

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
    return {"status": "healthy"}
