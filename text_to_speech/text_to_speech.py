import json
import os
import tempfile
import logging
import base64
import requests
from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse

# Setup logging
os.makedirs('/app/logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("/app/logs/text_to_speech.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Text To Speech API",
    description="API for Text-To-Speech Operations",
    version="1.0.0",
    docs_url="/",
)

# Constants
TTS_SERVER = os.getenv("TTS_SERVER", "http://localhost:8000")
CLONE_SPEAKER_API = f"{TTS_SERVER}/clone_speaker"
TTS_API = f"{TTS_SERVER}/tts"
TTS_STREAM_API = f"{TTS_SERVER}/tts_stream"
STUDIO_SPEAKERS_API = f"{TTS_SERVER}/studio_speakers"
LANGUAGES_API = f"{TTS_SERVER}/languages"


# Health check endpoint
@app.get("/health")
def health():
    try:
        # Add any specific service checks here
        return {"status": "healthy"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


# Helper function to check server availability
def is_server_available() -> bool:
    try:
        response = requests.get(f"{TTS_SERVER}/health", timeout=5)
        return response.status_code == 200
    except requests.RequestException:
        return False


@app.post("/clone_speaker")
async def clone_speaker(wav_file: UploadFile):
    if not is_server_available():
        logger.error("TTS server is unavailable for /clone_speaker.")
        raise HTTPException(status_code=503, detail="TTS server is unavailable. Please try again later.")

    try:
        logger.info("Cloning speaker...")
        files = {"wav_file": ("file.wav", await wav_file.read())}
        response = requests.post(CLONE_SPEAKER_API, files=files)
        response.raise_for_status()
        logger.info("Speaker cloned successfully.")
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Error cloning speaker: {e}")
        raise HTTPException(status_code=500, detail="Error cloning speaker. Please try again.")


@app.post("/tts")
async def tts(data: dict):
    if not is_server_available():
        logger.error("TTS server is unavailable for /tts.")
        raise HTTPException(status_code=503, detail="TTS server is unavailable. Please try again later.")

    try:
        logger.info(f"Performing TTS for text: {data.get('text', '')[:5]}...")
        response = requests.post(TTS_API, json=data)
        response.raise_for_status()

        base64_audio = response.content.strip(b'"')
        audio_data = base64.b64decode(base64_audio)

        temp_audio_path = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
        with open(temp_audio_path, "wb") as f:
            f.write(audio_data)

        logger.info(f"TTS completed successfully. Audio saved to {temp_audio_path}.")
        return FileResponse(temp_audio_path, media_type="audio/wav")
    except requests.RequestException as e:
        logger.error(f"Error performing TTS: {e}")
        raise HTTPException(status_code=500, detail="Error connecting to the TTS server. Please try again.")
    except Exception as e:
        logger.exception(f"Unexpected error in TTS endpoint: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred while processing your request.")


@app.post("/tts_stream")
async def tts_stream(data: dict):
    if not is_server_available():
        logger.error("TTS server is unavailable for /tts_stream.")
        raise HTTPException(status_code=503, detail="TTS server is unavailable. Please try again later.")

    try:
        logger.info("Starting TTS streaming...")

        def stream_audio():
            response = requests.post(TTS_STREAM_API, json=data, stream=True)
            response.raise_for_status()
            for chunk in response.iter_content(chunk_size=4096):
                yield chunk

        logger.info("TTS streaming started successfully.")
        return StreamingResponse(stream_audio(), media_type="audio/wav")
    except requests.RequestException as e:
        logger.error(f"Error streaming TTS: {e}")
        raise HTTPException(status_code=500, detail="Error streaming TTS. Please try again.")


@app.get("/studio_speakers")
async def studio_speakers():
    if not is_server_available():
        logger.error("TTS server is unavailable for /studio_speakers.")
        raise HTTPException(status_code=503, detail="TTS server is unavailable. Please try again later.")

    try:
        logger.info("Fetching studio speakers...")
        response = requests.get(STUDIO_SPEAKERS_API)
        response.raise_for_status()
        speakers = response.json()
        if not speakers:
            logger.warning("No studio speakers found.")
            return {"error": "No studio speakers available."}
        logger.info("Studio speakers fetched successfully.")
        return JSONResponse(content=speakers)
    except requests.RequestException as e:
        logger.error(f"Error fetching studio speakers: {e}")
        raise HTTPException(status_code=500, detail="Error fetching studio speakers. Please try again.")


@app.get("/languages")
async def languages():
    if not is_server_available():
        logger.error("TTS server is unavailable for /languages.")
        raise HTTPException(status_code=503, detail="TTS server is unavailable. Please try again later.")

    try:
        logger.info("Fetching supported languages...")
        response = requests.get(LANGUAGES_API)
        response.raise_for_status()
        languages = response.json()
        if not languages:
            logger.warning("No supported languages found.")
            return {"error": "No supported languages available."}
        logger.info("Supported languages fetched successfully.")
        return JSONResponse(content=languages)
    except requests.RequestException as e:
        logger.error(f"Error fetching languages: {e}")
        raise HTTPException(status_code=500, detail="Error fetching supported languages. Please try again.")
