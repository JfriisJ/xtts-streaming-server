import base64
import importlib
import io
import logging
import os
import tempfile
import wave
from contextlib import asynccontextmanager

import torch
import numpy as np
from typing import List
from pydantic import BaseModel

from fastapi import FastAPI, UploadFile, Body, HTTPException, Query, requests
from fastapi.responses import StreamingResponse
from requests import RequestException

from TTS.tts.configs.xtts_config import XttsConfig
from TTS.tts.models.xtts import Xtts
from TTS.utils.generic_utils import get_user_data_dir
from TTS.utils.manage import ModelManager

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def clear_gpu_cache():
    # clear the GPU cache
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

# Torch setup
torch.set_num_threads(int(os.environ.get("NUM_THREADS", os.cpu_count())))
device = torch.device("cuda" if os.environ.get("USE_CPU", "0") == "0" else "cpu")
if not torch.cuda.is_available() and device == "cuda":
    clear_gpu_cache()
    raise RuntimeError("CUDA device unavailable. Please use Dockerfile.cpu instead.")

# Maintain a mapping of engine names to configuration files
TTS_ENGINES = {
    "xtts": "xtts_config.py",
    "fastspeech2": "fastspeech2_config.py",
    "glow_tts": "glow_tts_config.py",
    "tacotron2": "tacotron2_config.py",
    "tacotron": "tacotron_config.py",
    "vits": "vits_config.py",
    "fast_pitch": "fast_pitch_config.py",
    "fast_speech": "fast_speech_config.py",
    "speedy_speech": "speedy_speech_config.py",
    "neuralhmm_tts": "neuralhmm_tts_config.py",
    "bark": "bark_config.py",
    "delightful_tts": "delightful_tts_config.py",
    "overflow": "overflow_config.py",
    "tortoise": "tortoise_config.py",
    "align_tts": "align_tts_config.py",
}

# Map model names to their corresponding files
TTS_MODELS = {
    "align_tts": "align_tts",
    "bark": "bark",
    "base_tacotron": "base_tacotron",
    "base_tts": "base_tts",
    "delightful_tts": "delightful_tts",
    "forward_tts": "forward_tts",
    "glow_tts": "glow_tts",
    "neuralhmm_tts": "neuralhmm_tts",
    "overflow": "overflow",
    "tacotron": "tacotron",
    "tacotron2": "tacotron2",
    "tortoise": "tortoise",
    "vits": "vits",
    "xtts": "xtts",
}


custom_model_path = os.environ.get("CUSTOM_MODEL_PATH", "/app/tts_models")
if os.path.exists(custom_model_path) and os.path.isfile(custom_model_path + "/config.json"):
    model_path = custom_model_path
else:
    # Cache for loaded models
    model_name = "tts_models/multilingual/multi-dataset/xtts_v2"
    ModelManager().download_model(model_name)
    model_path = os.path.join(get_user_data_dir("tts"), model_name.replace("/", "--"))

config = XttsConfig()
config.load_json(os.path.join(model_path, "config.json"))
model = Xtts.init_from_config(config)
model.load_checkpoint(config, checkpoint_dir=model_path, eval=True, use_deepspeed=True if device == "cuda" else False)
model.to(device)

# # FastAPI application
# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     try:
#         logger.info("Starting XTTS Server...")
#         yield
#     finally:
#         logger.info("Shutting down XTTS Server.")

app = FastAPI(
    title="XTTS Server",
    version="0.0.1",
    docs_url="/",
)

# Cache for loaded models
loaded_models = {}


def load_model(model_name):
    """Dynamically load the TTS model based on the model name."""
    if model_name not in TTS_MODELS:
        raise ValueError(f"Model '{model_name}' not supported.")

    if model_name in loaded_models:
        return loaded_models[model_name]

    # Dynamically import the model module
    model_module = importlib.import_module(f"TTS.tts.models.{TTS_MODELS[model_name]}")
    model_class = getattr(model_module, model_name.capitalize())

    # Initialize the model
    model = model_class.init_from_config(config)
    model.load_checkpoint(
        config,
        checkpoint_dir=model_path,
        eval=True,
        use_deepspeed=True if device == "cuda" else False,
    )
    model.to(device)

    loaded_models[model_name] = model
    return model

def load_tts_engine(engine_name):
    """Load the TTS engine dynamically based on the engine name."""
    if engine_name not in TTS_ENGINES:
        raise ValueError(f"Engine '{engine_name}' not supported.")

    if engine_name in loaded_models:
        return loaded_models[engine_name]

    config_module_path = os.path.join(custom_model_path, TTS_ENGINES[engine_name])
    config = XttsConfig()
    config.load_json(config_module_path)

    model = Xtts.init_from_config(config)
    model.load_checkpoint(
        config,
        checkpoint_dir=model_path,
        eval=True,
        use_deepspeed=True if device == "cuda" else False,
    )
    model.to(device)
    loaded_models[engine_name] = (model, config)
    return model, config

def postprocess(wav):
    """Post process the output waveform"""
    if isinstance(wav, list):
        wav = torch.cat(wav, dim=0)
    wav = wav.clone().detach().cpu().numpy()
    wav = wav[None, : int(wav.shape[0])]
    wav = np.clip(wav, -1, 1)
    wav = (wav * 32767).astype(np.int16)
    return wav


def encode_audio_common(
    frame_input, encode_base64=True, sample_rate=24000, sample_width=2, channels=1
):
    """Return base64 encoded audio"""
    wav_buf = io.BytesIO()
    with wave.open(wav_buf, "wb") as vfout:
        vfout.setnchannels(channels)
        vfout.setsampwidth(sample_width)
        vfout.setframerate(sample_rate)
        vfout.writeframes(frame_input)

    wav_buf.seek(0)
    if encode_base64:
        b64_encoded = base64.b64encode(wav_buf.getbuffer()).decode("utf-8")
        return b64_encoded
    else:
        return wav_buf.read()


class StreamingInputs(BaseModel):
    speaker_embedding: List[float]
    gpt_cond_latent: List[List[float]]
    text: str
    language: str
    add_wav_header: bool = True
    stream_chunk_size: str = "20"


def predict_streaming_generator(parsed_input: dict = Body(...)):
    speaker_embedding = torch.tensor(parsed_input.speaker_embedding).unsqueeze(0).unsqueeze(-1)
    gpt_cond_latent = torch.tensor(parsed_input.gpt_cond_latent).reshape((-1, 1024)).unsqueeze(0)
    text = parsed_input.text
    language = parsed_input.language

    stream_chunk_size = int(parsed_input.stream_chunk_size)
    add_wav_header = parsed_input.add_wav_header


    chunks = model.inference_stream(
        text,
        language,
        gpt_cond_latent,
        speaker_embedding,
        stream_chunk_size=stream_chunk_size,
        enable_text_splitting=True
    )

    for i, chunk in enumerate(chunks):
        try:
            print(f"Processing chunk {i}")
            chunk = postprocess(chunk)
            if i == 0 and add_wav_header:
                yield encode_audio_common(b"", encode_base64=False)
                yield chunk.tobytes()
            else:
                yield chunk.tobytes()
        except Exception as e:
            print(f"Error in streaming generator at chunk {i}: {e}")
            break

class TTSInputs(BaseModel):
    speaker_embedding: List[float]
    gpt_cond_latent: List[List[float]]
    text: str
    language: str

@app.post("/tts")
def predict_speech_dynamic(parsed_input: TTSInputs, model_name: str = Query("xtts", enum=TTS_MODELS.keys())):
    """Dynamically select the TTS model and generate speech."""
    try:
        model = load_model(model_name)
        speaker_embedding = torch.tensor(parsed_input.speaker_embedding).unsqueeze(0).unsqueeze(-1)
        gpt_cond_latent = torch.tensor(parsed_input.gpt_cond_latent).reshape((-1, 1024)).unsqueeze(0)
        text = parsed_input.text
        language = parsed_input.language

        out = model.inference(
            text,
            language,
            gpt_cond_latent,
            speaker_embedding,
        )

        wav = postprocess(torch.tensor(out["wav"]))
        return encode_audio_common(wav.tobytes())
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        return {"error": str(e)}


@app.get("/health")
def health_check():
    """Check server health and model availability."""
    try:
        health_status = {
            "server": "running",
            "models_loaded": list(loaded_models.keys()),
            "cuda_available": torch.cuda.is_available(),
        }
        return health_status
    except Exception as e:
        return {"server": "error", "details": str(e)}


SERVER_URL = os.getenv("SERVER_URL","http://localhost:80")  # Replace with your server URL
def warmup_server():
    """
    Warms up the server by sending a streaming request to /tts_stream.
    Fetches test data from /example_streaming_input.
    """
    try:
        logger.info("Fetching example input for warmup.")
        example_input = requests.get(SERVER_URL + "/example_streaming_input").json()
        logger.info("Sending warmup request to /tts_stream.")
        with requests.post(
            SERVER_URL + "/tts_stream",
            json=example_input,
            stream=True,
        ) as resp:
            if resp.status_code == 200:
                logger.info("Warmup streaming response received successfully.")
                for chunk in resp.iter_content(chunk_size=1024):
                    logger.debug(f"Received audio chunk of size {len(chunk)} bytes")
            else:
                logger.error(f"Error in warmup request: {resp.status_code} - {resp.text}")
    except RequestException as req_error:
        logger.error(f"Warmup request failed: {req_error}")
    except Exception as e:
        logger.error(f"Unexpected error in warmup_server: {e}")


warmup_server()
