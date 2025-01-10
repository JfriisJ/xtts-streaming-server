from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
import requests
import os
import tempfile
import logging
import base64

# Setup logging
os.makedirs('/app/logs', exist_ok=True)
logging.basicConfig(
    level=logging.DEBUG,
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

TTS_SERVER = os.getenv("TTS_SERVER", "http://localhost:8000")
CLONE_SPEAKER_API = f"{TTS_SERVER}/clone_speaker"
TTS_API = f"{TTS_SERVER}/tts"
TTS_STREAM_API = f"{TTS_SERVER}/tts_stream"
STUDIO_SPEAKERS_API = f"{TTS_SERVER}/studio_speakers"
LANGUAGES_API = f"{TTS_SERVER}/languages"


@app.post("/clone_speaker")
async def clone_speaker(wav_file: UploadFile):
    """Clones a speaker using the /clone_speaker endpoint."""
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
    """Performs TTS using the /tts endpoint."""
    try:
        logger.info(f"Performing TTS for text: {data.get('text', '')[:50]}...")
        response = requests.post(TTS_API, json=data)
        response.raise_for_status()
        audio_data = response.json().get("audio")
        if not audio_data:
            logger.error("No audio data returned by the TTS server.")
            raise HTTPException(status_code=500, detail="No audio data returned by the TTS server.")

        temp_audio_path = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
        with open(temp_audio_path, "wb") as f:
            f.write(base64.b64decode(audio_data))

        logger.info(f"TTS completed. Audio saved to {temp_audio_path}.")
        return FileResponse(temp_audio_path, media_type="audio/wav")
    except requests.RequestException as e:
        logger.error(f"Error performing TTS: {e}")
        raise HTTPException(status_code=500, detail="Error performing TTS. Please check your input and try again.")


@app.post("/tts_stream")
async def tts_stream(data: dict):
    """Streams TTS audio using the /tts_stream endpoint."""
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
    """Fetches studio speakers."""
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
    """Fetches supported languages."""
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


@app.get("/health")
async def health_check():
    """Health check endpoint for TTS service."""
    logger.info("Health check passed.")
    return {"status": "healthy"}
