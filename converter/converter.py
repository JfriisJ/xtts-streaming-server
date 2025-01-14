from bs4 import BeautifulSoup
from fastapi import FastAPI, UploadFile, HTTPException
import os
import subprocess
import logging
import zipfile
from xml.etree.ElementTree import parse
import re

from md_2_json import parse_markdown_to_json
from html_2_json import parse_html_to_json
from odt_2_json import parse_odt_to_json

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


@app.post("/convert")
async def convert(file: UploadFile):
    input_path = os.path.join(UPLOAD_FOLDER, file.filename)
    logger.info(f"Converting file: {file.filename}")

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
