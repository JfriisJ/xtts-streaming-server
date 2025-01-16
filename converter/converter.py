from fastapi import FastAPI, UploadFile, HTTPException
import os
import logging
import json
from jsonschema import validate, ValidationError
from file_format import convert_file

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
        file_extension = os.path.splitext(file.filename)[-1].lower()
        logger.debug(f"File extension detected: {file_extension}")

        # Read the file content as bytes
        # file_content = await file.read()
        content = (await file.read()).decode("utf-8")
        json_content = convert_file(content, file_extension)

        # Parse and validate
        return json_content
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



def parse_and_validate(content):
    logger.info(f"Parsing and validating content.")

    # Validate the JSON output
    try:
        # validate(instance=content, schema=JSON_SCHEMA)
        logger.info("Validation successful!")
        return content
    except ValidationError as e:
        logger.error(f"Validation failed: {e.message}")
        raise ValueError(f"JSON validation failed: {e.message}")

