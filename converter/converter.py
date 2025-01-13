from bs4 import BeautifulSoup
from fastapi import FastAPI, UploadFile, HTTPException
import os
import subprocess
import logging
import zipfile
from xml.etree.ElementTree import parse
import re

from md_2_json import parse_markdown_to_json

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

def parse_epub_to_json(file_path):
    """
    Parse EPUB files into a structured JSON format.
    """
    try:
        with zipfile.ZipFile(file_path, 'r') as epub_zip:
            # Look for the main content file in the EPUB
            container = epub_zip.read('META-INF/container.xml')
            tree = parse(container)
            root_file_path = tree.find('.//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile').attrib['full-path']
            content = epub_zip.read(root_file_path).decode('utf-8')

        return parse_html_to_json(content)

    except Exception as e:
        logger.error(f"Error parsing EPUB: {e}")
        raise HTTPException(status_code=500, detail="Error parsing EPUB file.")

def parse_html_to_json(html_content):
    """
    Parse HTML content into structured JSON.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    sections = []

    def parse_section(tag, level=1):
        section = {
            "Heading": tag.get_text(strip=True),
            "Content": "",
            "Subsections": []
        }
        next_level_tags = tag.find_all(f'h{level + 1}')
        for sub_tag in next_level_tags:
            subsection = parse_section(sub_tag, level + 1)
            section["Subsections"].append(subsection)
        return section

    # Identify the main headings (e.g., h1)
    main_headings = soup.find_all('h1')
    for heading in main_headings:
        sections.append(parse_section(heading, 1))

    return {
        "Title": soup.title.string if soup.title else "Untitled",
        "Sections": sections
    }


@app.post("/convert")
async def convert(file: UploadFile):
    input_path = os.path.join(UPLOAD_FOLDER, file.filename)

    try:
        with open(input_path, "wb") as f:
            f.write(await file.read())

        if file.filename.endswith(".md"):
            with open(input_path, "r", encoding="utf-8") as md_file:
                content = md_file.read()
            json_output = parse_markdown_to_json(content)

        elif file.filename.endswith(".epub"):
            json_output = parse_epub_to_json(input_path)

        elif file.filename.endswith(".html"):
            with open(input_path, "r", encoding="utf-8") as html_file:
                content = html_file.read()
            json_output = parse_html_to_json(content)

        else:
            raise HTTPException(status_code=400, detail="Unsupported file type")

        return {"message": "Conversion successful", "json_output": json_output}

    except Exception as e:
        logger.error(f"Error converting file: {e}")
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
