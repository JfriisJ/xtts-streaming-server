from fastapi import FastAPI, UploadFile, HTTPException
import os
import subprocess
import logging

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
    description="Your API Description",
    version="0.0.1",
    docs_url="/",
)
UPLOAD_FOLDER = "/app/uploads"
OUTPUT_FOLDER = "/app/outputs"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


@app.post("/convert")
async def convert(file: UploadFile):
    """Converts a file to ODT format."""
    input_path = os.path.join(UPLOAD_FOLDER, file.filename)
    output_path = os.path.join(OUTPUT_FOLDER, f"{os.path.splitext(file.filename)[0]}.odt")
    try:
        with open(input_path, "wb") as f:
            f.write(await file.read())

        if file.filename.endswith(".epub"):
            subprocess.run(
                ["pandoc", input_path, "-f", "epub", "-t", "odt", "-o", output_path],
                check=True
            )
        else:
            subprocess.run(
                ["libreoffice", "--headless", "--convert-to", "odt", "--outdir", OUTPUT_FOLDER, input_path],
                check=True
            )

        if not os.path.exists(output_path):
            raise HTTPException(status_code=500, detail="Output file not created")

        return {"message": "Conversion successful", "output_path": output_path}
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Conversion failed: {e}")
    finally:
        if os.path.exists(input_path):
            os.remove(input_path)