import io
import json
import os
from pathlib import Path
from threading import Lock
from typing import Union

from TTS.config import load_config
from TTS.utils.manage import ModelManager
from TTS.utils.synthesizer import Synthesizer
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse


# Static argument configuration from server.py
class Config:
    LIST_MODELS = False
    MODEL_NAME = "tts_models/en/vctk/vits"
    VOCODER_NAME = None
    CONFIG_PATH = None
    MODEL_PATH = None
    VOCODER_PATH = None
    VOCODER_CONFIG_PATH = None
    SPEAKERS_FILE_PATH = None
    PORT = 5002
    USE_CUDA = True
    DEBUG = False
    SHOW_DETAILS = False

# Initialize model manager
path = Path(__file__).parent / "../.models.json"
manager = ModelManager(path)

if Config.LIST_MODELS:
    manager.list_models()
    exit()

# Load pre-trained model paths
model_path = Config.MODEL_PATH
config_path = Config.CONFIG_PATH
speakers_file_path = Config.SPEAKERS_FILE_PATH
vocoder_path = Config.VOCODER_PATH
vocoder_config_path = Config.VOCODER_CONFIG_PATH

if Config.MODEL_NAME and not Config.MODEL_PATH:
    model_path, config_path, model_item = manager.download_model(Config.MODEL_NAME)
    Config.VOCODER_NAME = model_item["default_vocoder"] if Config.VOCODER_NAME is None else Config.VOCODER_NAME

if Config.VOCODER_NAME and not Config.VOCODER_PATH:
    vocoder_path, vocoder_config_path, _ = manager.download_model(Config.VOCODER_NAME)

# Load synthesizer
synthesizer = Synthesizer(
    tts_checkpoint=model_path,
    tts_config_path=config_path,
    tts_speakers_file=speakers_file_path,
    tts_languages_file=None,
    vocoder_checkpoint=vocoder_path,
    vocoder_config=vocoder_config_path,
    encoder_checkpoint="",
    encoder_config="",
    use_cuda=Config.USE_CUDA,
)

use_multi_speaker = hasattr(synthesizer.tts_model, "num_speakers") and (
    synthesizer.tts_model.num_speakers > 1 or synthesizer.tts_speakers_file is not None
)
speaker_manager = getattr(synthesizer.tts_model, "speaker_manager", None)

use_multi_language = hasattr(synthesizer.tts_model, "num_languages") and (
    synthesizer.tts_model.num_languages > 1 or synthesizer.tts_languages_file is not None
)
language_manager = getattr(synthesizer.tts_model, "language_manager", None)

use_gst = synthesizer.tts_config.get("use_gst", False)
lock = Lock()

# Initialize FastAPI app
app = FastAPI(
    title="XTTS Streaming Server",
    description="XTTS Streaming Server",
    version="0.0.1",
    docs_url="/",
)

def style_wav_uri_to_dict(style_wav: str) -> Union[str, dict]:
    """Transform a style_wav URI into a dict or string."""
    if style_wav:
        if os.path.isfile(style_wav) and style_wav.endswith(".wav"):
            return style_wav

        style_wav = json.loads(style_wav)
        return style_wav
    return None

@app.get("/")
def index():
    return {
        "show_details": Config.SHOW_DETAILS,
        "use_multi_speaker": use_multi_speaker,
        "use_multi_language": use_multi_language,
        "speaker_ids": speaker_manager.name_to_id if speaker_manager else None,
        "language_ids": language_manager.name_to_id if language_manager else None,
        "use_gst": use_gst,
    }

@app.get("/details")
def details():
    model_config = load_config(config_path) if config_path else {}
    vocoder_config = load_config(vocoder_config_path) if vocoder_config_path else {}

    return {
        "show_details": Config.SHOW_DETAILS,
        "model_config": model_config,
        "vocoder_config": vocoder_config,
    }

@app.post("/api/tts")
def tts(request: Request):
    with lock:
        text = request.headers.get("text", "")
        speaker_idx = request.headers.get("speaker-id", "")
        language_idx = request.headers.get("language-id", "")
        style_wav = request.headers.get("style-wav", "")
        style_wav = style_wav_uri_to_dict(style_wav)

        wavs = synthesizer.tts(
            text,
            speaker_name=speaker_idx,
            language_name=language_idx,
            style_wav=style_wav,
        )
        out = io.BytesIO()
        synthesizer.save_wav(wavs, out)
        out.seek(0)

    return StreamingResponse(out, media_type="audio/wav")

@app.get("/locales")
def mary_tts_api_locales():
    locale = Config.MODEL_NAME.split("/")[1] if Config.MODEL_NAME else "en"
    return {"locale": locale}

@app.get("/voices")
def mary_tts_api_voices():
    name = Config.MODEL_NAME.split("/")[3] if Config.MODEL_NAME else "default"
    locale = Config.MODEL_NAME.split("/")[1] if Config.MODEL_NAME else "en"
    return {"name": name, "locale": locale, "gender": "u"}

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.get("/languages")
def get_languages():
    return language_manager.name_to_id if language_manager else {}

@app.get("/studio_speakers")
def get_speakers():
    return (
        {speaker: speaker_manager.speakers[speaker] for speaker in speaker_manager.speakers.keys()}
        if speaker_manager and hasattr(speaker_manager, "speakers")
        else {}
    )

