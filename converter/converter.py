import subprocess

from bs4 import BeautifulSoup
from fastapi import FastAPI, UploadFile, HTTPException
import os
import logging
import json
from jsonschema import validate, ValidationError

# Import parsers for supported file types

from md_2_json import parse_markdown_to_json
from html_2_json import parse_html_to_json, parse_epub_to_json

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
    description="Converts various document formats to structured JSON.",
    version="0.0.2",
    docs_url="/",
)

UPLOAD_FOLDER = "/app/uploads"
OUTPUT_FOLDER = "/app/outputs"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Load schema once globally
with open("json_schema.json", "r") as f:
    JSON_SCHEMA = json.load(f)

@app.post("/convert")
async def convert(file: UploadFile):
    logger.info(f"Received file: {file.filename}")
    try:
        file_extension = file.filename.split(".")[-1].lower()
        logger.debug(f"File extension detected: {file_extension}")

        if file_extension == "md":
            content = (await file.read()).decode("utf-8")
            logger.info("Processing Markdown file.")
            return {"message": "Conversion successful", "json_output": parse_markdown_to_json(content)}

        elif file_extension == "html":
            content = (await file.read()).decode("utf-8")
            logger.info("Processing HTML file.")
            return {"message": "Conversion successful", "json_output": parse_html_to_json(content)}

        elif file_extension == "epub":
            file_path = f"/tmp/{file.filename}"
            with open(file_path, "wb") as f:
                f.write(await file.read())
            logger.info("Processing EPUB file.")
            return {"message": "Conversion successful", "json_output": parse_epub_to_json(file_path)}

        elif file_extension == "odt":
            file_path = f"/tmp/{file.filename}"
            with open(file_path, "wb") as f:
                f.write(await file.read())
            logger.info("Processing ODT file.")
            html_path = convert_odt_to_html(file_path, "/tmp")
            return {"message": "Conversion successful", "json_output": parse_html_to_json(html_path)}

        elif file_extension == "pdf":
            file_path = f"/tmp/{file.filename}"
            with open(file_path, "wb") as f:
                f.write(await file.read())
            logger.info("Processing PDF file.")
            html_path = convert_pdf_to_html(file_path, "/tmp")
            return {"message": "Conversion successful", "json_output": parse_html_to_json(html_path)}

        else:
            logger.warning(f"Unsupported file format: {file_extension}")
            raise HTTPException(status_code=400, detail=f"Unsupported file format: {file_extension}")

    except Exception as e:
        logger.error(f"Error converting file {file.filename}: {e}")
        raise HTTPException(status_code=500, detail="Conversion failed.")

@app.get("/health")
def health():
    """
    Health check endpoint for the API.
    """
    try:
        logger.info("Health check requested.")
        return {"status": "healthy"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}

def convert_pdf_to_html(pdf_path, output_dir):
    """
    Convert a PDF file to HTML using LibreOffice or pdftohtml.
    """
    logger.debug(f"Starting PDF to HTML conversion for {pdf_path}")
    try:
        subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "html", pdf_path, "--outdir", output_dir],
            check=True
        )
        html_path = os.path.join(output_dir, os.path.splitext(os.path.basename(pdf_path))[0] + ".html")
        if not os.path.exists(html_path):
            logger.error(f"Conversion failed. HTML file not found: {html_path}")
            raise RuntimeError(f"Conversion failed. HTML file not found: {html_path}")
        logger.info(f"PDF to HTML conversion successful: {html_path}")
        return html_path
    except subprocess.CalledProcessError as e:
        logger.error(f"LibreOffice conversion failed: {e}")
        raise RuntimeError(f"LibreOffice conversion failed: {e}")


import shutil


def convert_odt_to_html(odt_path, output_dir):
    """
    Convert an ODT file to HTML using LibreOffice.
    """
    if not shutil.which("libreoffice"):
        raise RuntimeError("LibreOffice is not installed or not in PATH.")

    logger.debug(f"Starting ODT to HTML conversion for {odt_path}")
    try:
        subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "html", odt_path, "--outdir", output_dir],
            check=True
        )
        html_path = os.path.join(output_dir, os.path.splitext(os.path.basename(odt_path))[0] + ".html")
        if not os.path.exists(html_path):
            logger.error(f"Conversion failed. HTML file not found: {html_path}")
            raise RuntimeError(f"Conversion failed. HTML file not found: {html_path}")
        logger.info(f"ODT to HTML conversion successful: {html_path}")
        return html_path
    except subprocess.CalledProcessError as e:
        logger.error(f"LibreOffice conversion failed: {e}")
        raise RuntimeError(f"LibreOffice conversion failed: {e}")


def post_process_html(html_path):
    """
    Post-process HTML to standardize structure and fix formatting issues.
    """
    with open(html_path, "r", encoding="utf-8") as file:
        html_content = file.read()

    soup = BeautifulSoup(html_content, "html.parser")

    # Standardize headings and ensure correct hierarchy
    for i in range(1, 7):  # Loop through h1 to h6
        for tag in soup.find_all(f"h{i}"):
            tag.name = f"h{i}"  # Enforce consistent tag names

    # Example cleanup: removing unwanted elements
    for unwanted_tag in soup(["footer", "header", "script", "style"]):
        unwanted_tag.decompose()

    # Return cleaned-up HTML content
    return str(soup)

def parse_and_validate(file_path, file_extension):
    """
    Parse the file and validate the output against the JSON schema.
    """
    logger.info(f"Parsing and validating file: {file_path} with extension: {file_extension}")
    if file_extension == ".md":
        with open(file_path, "r", encoding="utf-8") as file:
            content = file.read()
        json_output = parse_markdown_to_json(content)

    elif file_extension == ".epub":
        json_output = parse_epub_to_json(file_path)

    elif file_extension == ".html":
        with open(file_path, "r", encoding="utf-8") as file:
            content = file.read()
        json_output = parse_html_to_json(content)

    elif file_extension == ".odt":
        # Convert ODT to HTML using LibreOffice
        output_dir = os.path.dirname(file_path)
        html_path = convert_odt_to_html(file_path, output_dir)
        json_output = parse_html_to_json(html_path)

    elif file_extension == ".pdf":
        # Convert PDF to HTML using LibreOffice
        output_dir = os.path.dirname(file_path)
        html_path = convert_pdf_to_html(file_path, output_dir)
        json_output = parse_html_to_json(html_path)

    else:
        logger.error(f"Unsupported file type: {file_extension}")
        raise ValueError("Unsupported file type")

    # Validate the JSON output
    try:
        validate(instance=json_output, schema=JSON_SCHEMA)
        logger.info("Validation successful!")
        logger.debug(json_output)
    except ValidationError as e:
        logger.error(f"Validation failed: {e.message}")
        logger.error(f"JSON output: {json_output}")
        raise ValueError(f"JSON validation failed: {e.message}")

    return json_output
