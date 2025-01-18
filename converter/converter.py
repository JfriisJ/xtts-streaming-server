from fastapi import FastAPI, UploadFile, HTTPException
import os
import logging
from converters.md_to_json import md_to_json
from spellcheck import process_json_content


# Setup logging
os.makedirs('/app/logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
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


@app.post("/convert")
async def convert(file: UploadFile):
    logger.info(f"Received file: {file.filename}")
    try:
        file_extension = os.path.splitext(file.filename)[-1].lower()
        logger.debug(f"File extension detected: {file_extension}")

        # Read the file content as bytes and decode
        content = (await file.read()).decode("utf-8")

        # Convert Markdown to JSON
        json_content = md_to_json(content)

        # Process spell checking on JSON content
        processed_content = process_json_content(json_content["Sections"])

        logger.info(f"Spell-checked content: {processed_content}")

        # Update JSON content with spell-checked data
        json_content["Sections"] = processed_content

        return json_content  # Return processed JSON content
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


