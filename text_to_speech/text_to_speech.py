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
    title="Text To speech API",
    description="Your API Description",
    version="0.0.1",
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
        files = {"wav_file": ("file.wav", await wav_file.read())}
        response = requests.post(CLONE_SPEAKER_API, files=files)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Error cloning speaker: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tts")
async def tts(data: dict):
    """Performs TTS using the /tts endpoint."""
    try:
        response = requests.post(TTS_API, json=data)
        response.raise_for_status()
        audio_data = response.json().get("audio")
        if not audio_data:
            raise HTTPException(status_code=500, detail="No audio data returned")

        temp_audio_path = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
        with open(temp_audio_path, "wb") as f:
            f.write(base64.b64decode(audio_data))

        return FileResponse(temp_audio_path, media_type="audio/wav")
    except requests.RequestException as e:
        logger.error(f"Error generating TTS: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tts_stream")
async def tts_stream(data: dict):
    """Streams TTS audio using the /tts_stream endpoint."""
    try:
        def stream_audio():
            response = requests.post(TTS_STREAM_API, json=data, stream=True)
            response.raise_for_status()
            for chunk in response.iter_content(chunk_size=4096):
                yield chunk

        return StreamingResponse(stream_audio(), media_type="audio/wav")
    except requests.RequestException as e:
        logger.error(f"Error streaming TTS: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/studio_speakers")
async def studio_speakers():
    """Fetches studio speakers."""
    try:
        response = requests.get(STUDIO_SPEAKERS_API)
        response.raise_for_status()
        return JSONResponse(content=response.json())
    except requests.RequestException as e:
        logger.error(f"Error fetching studio speakers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/languages")
async def languages():
    """Fetches supported languages."""
    try:
        response = requests.get(LANGUAGES_API)
        response.raise_for_status()
        return JSONResponse(content=response.json())
    except requests.RequestException as e:
        logger.error(f"Error fetching languages: {e}")
        raise HTTPException(status_code=500, detail=str(e))
