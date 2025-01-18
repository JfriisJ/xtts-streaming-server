import torch
import io
import json
import os
import tempfile
import base64
import wave
import numpy as np
import requests
import logging

from pathlib import Path
from typing import Any
from requests import RequestException
from typing import Union
from fastapi import FastAPI, UploadFile, HTTPException, Query
from contextlib import asynccontextmanager
from fastapi.responses import StreamingResponse
from typing import List
from pydantic import BaseModel, field_validator, Field
from fastapi import Body
from typing import Optional

from TTS.TTS.config import load_config
from TTS.TTS.utils.manage import ModelManager
from TTS.TTS.utils.synthesizer import Synthesizer



logger = logging.getLogger(__name__)

# Global variables for model and config
model = None
config = None

# Global variables to manage active model and configuration
active_model: Any = None
active_model_name: str = ""


# FastAPI app with lifespan

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle manager for application startup and shutdown.
    """
    global model, config
    try:
        logger.info("Starting application...")
        # Initialize model and config
        model, config = load_model(custom_model_path="/app/tts_models", use_cuda=False)
        logger.info("Model loaded successfully.")
        yield  # Application is ready to accept requests
    except Exception as e:
        logger.error(f"Error during application startup: {e}")
        raise RuntimeError("Startup failed.")
    finally:
        # Add any necessary cleanup tasks
        logger.info("Shutting down application...")
        logger.info("Application shutdown complete.")

logger.info("Running XTTS Server ...", flush=True)
app = FastAPI(
    title="TTS server",
    description="TTS Streaming server",
    version="0.0.1",
    lifespan=lifespan
)

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

# Path to Coqui .models.json
models_json_path = Path(__file__).resolve().parent / "TTS" / "TTS" / ".models.json"
if not models_json_path.is_file():
    raise FileNotFoundError(f"Configuration file not found at: {models_json_path}")

# Initialize Coqui ModelManager
manager = ModelManager(models_json_path)

# Extended configuration
class TTSConfig(BaseModel):
    list_models: bool = True
    model_name: str = "tts_models/en/ljspeech/tacotron2-DDC"
    vocoder_name: Optional[str] = None
    config_path: Optional[str] = None
    model_path: Optional[str] = None
    vocoder_path: Optional[str] = None
    vocoder_config_path: Optional[str] = None
    speakers_file_path: Optional[str] = None
    port: int = 5002
    use_cuda: bool = False
    debug: bool = False
    show_details: bool = False

# Initialize app-specific configuration
app_config = TTSConfig()

class ModelConfig(BaseModel):
    active_model: str = "default_model_name"
    active_vocoder: str = "default_vocoder_name"

# Initialize global model configuration
model_config = ModelConfig()



class StreamingInputs(BaseModel):
    """
    Input schema for streaming TTS synthesis.
    """
    speaker_embedding: List[float] = Field(..., description="Speaker embedding vector.")
    gpt_cond_latent: List[List[float]] = Field(..., description="GPT conditioning latents.")
    text: str = Field(..., description="Input text for synthesis.", min_length=1)
    language: str = Field(..., description="Language code (e.g., 'en').", min_length=2, max_length=5)
    add_wav_header: bool = Field(True, description="Whether to add WAV header.")
    stream_chunk_size: int = Field(20, description="Chunk size in ms.", ge=10, le=200)

    @field_validator("stream_chunk_size")
    @classmethod
    def validate_chunk_size(cls, value):
        if not (10 <= value <= 200):
            raise ValueError("Chunk size must be between 10 and 200 milliseconds.")
        return value


class TTSInputs(BaseModel):
    """
    Input schema for single TTS synthesis.
    """
    speaker_embedding: List[float]
    gpt_cond_latent: List[List[float]]
    text: str
    language: str


def predict_streaming_generator(parsed_input: dict = Body(...)):
    """
    Generator to stream TTS audio chunks dynamically based on the active model.
    """
    global active_model

    if not active_model:
        raise ValueError("No active model set. Please set a model using '/set_model'.")

    try:
        # Validate input schema
        validated_input = StreamingInputs(**parsed_input)

        # Prepare inputs for inference
        speaker_embedding = torch.tensor(validated_input.speaker_embedding).unsqueeze(0).unsqueeze(-1)
        gpt_cond_latent = torch.tensor(validated_input.gpt_cond_latent).reshape((-1, 1024)).unsqueeze(0)

        # Dynamically use the active model for inference
        chunks = active_model.inference_stream(
            text=validated_input.text,
            language=validated_input.language,
            gpt_cond_latent=gpt_cond_latent,
            speaker_embedding=speaker_embedding,
            stream_chunk_size=validated_input.stream_chunk_size,
            enable_text_splitting=True,
        )

        for i, chunk in enumerate(chunks):
            try:
                logger.debug(f"Processing chunk {i}")
                processed_chunk = postprocess(chunk)
                yield processed_chunk.tobytes()
            except Exception as e:
                logger.error(f"Error processing chunk {i}: {e}")
                break

    except Exception as e:
        logger.error(f"Error in streaming generator: {e}")
        raise
    finally:
        logger.info("Streaming completed.")



def set_active_model(model_name: str, use_cuda: bool = False):
    """
    Load and set the active model dynamically based on the provided name.
    """
    global active_model, active_model_name

    try:
        active_model, config = load_model(model_name=model_name, use_cuda=use_cuda)
        active_model_name = model_name
        return {"message": f"Model '{model_name}' loaded successfully.", "config": config.dict()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load model '{model_name}': {str(e)}")

# model_loader.py
def load_model(model_name: str, vocoder_name: str = None):
    """
    Dynamically load the specified TTS model and vocoder.
    """
    manager = ModelManager()

    # Download and configure the model
    model_path, config_path, model_item = manager.download_model(model_name)
    if vocoder_name is None:
        vocoder_name = model_item.get("default_vocoder")

    # Download and configure the vocoder if specified
    vocoder_path, vocoder_config_path = None, None
    if vocoder_name:
        vocoder_path, vocoder_config_path, _ = manager.download_model(vocoder_name)

    # Load the synthesizer
    synthesizer = Synthesizer(
        tts_checkpoint=model_path,
        tts_config_path=config_path,
        vocoder_checkpoint=vocoder_path,
        vocoder_config=vocoder_config_path,
        use_cuda=True,
    )
    return synthesizer



@app.get("/models", summary="List Available Models", tags=["Models"])
async def list_models():
    """
    List all available models in the TTS models directory.
    """
    try:
        models_dir = Path(__file__).resolve().parent / "TTS" / "tts" / "models"

        if not models_dir.exists():
            raise FileNotFoundError(f"Models directory not found at {models_dir}")

        models = [item.name for item in models_dir.iterdir() if item.is_dir()]
        return {"models": models}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing models: {str(e)}")


@app.post("/set_model", summary="Set Active Model", tags=["Models"])
async def set_model(model_name: str, use_cuda: bool = False):
    """
    API endpoint to dynamically set the active model.
    """
    try:
        response = set_active_model(model_name=model_name, use_cuda=use_cuda)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))





@app.get("/details", summary="Get Model and Vocoder Details", tags=["Info"])
async def get_details():
    """
    Retrieve details of the currently active model and vocoder.
    """
    try:
        # Fetch the active model and vocoder from the global configuration
        model_config = None
        vocoder_config = None

        # Load model configuration if available
        if app_config.config_path and os.path.isfile(app_config.config_path):
            model_config = load_config(app_config.config_path)
        elif app_config.model_name:
            model_item = manager.get_model_item(app_config.model_name)
            if model_item:
                model_config = model_item

        # Load vocoder configuration if available
        if app_config.vocoder_config_path and os.path.isfile(app_config.vocoder_config_path):
            vocoder_config = load_config(app_config.vocoder_config_path)
        elif app_config.vocoder_name:
            vocoder_item = manager.get_model_item(app_config.vocoder_name)
            if vocoder_item:
                vocoder_config = vocoder_item

        if not model_config and not vocoder_config:
            raise HTTPException(status_code=404, detail="No active model or vocoder found.")

        return {
            "model_config": model_config,
            "vocoder_config": vocoder_config,
            "additional_info": {
                "active_model": app_config.model_name,
                "active_vocoder": app_config.vocoder_name,
                "use_cuda": app_config.use_cuda,
                "show_details": app_config.show_details,
            },
        }

    except Exception as e:
        logger.error(f"Error retrieving details: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving details: {str(e)}")


@app.post("/tts_stream", summary="Synthesize Speech (Streaming)")
async def tts_stream(parsed_input: dict = Query(...)):
    """
    Endpoint for streaming text-to-speech synthesis.
    """
    try:
        return StreamingResponse(
            predict_streaming_generator(model, parsed_input),
            media_type="audio/wav",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=handle_error(e))

@app.post("/tts", summary="Synthesize Speech", tags=["TTS"])
async def tts(
    text: str = Query(..., description="Input text to synthesize"),
    speaker_id: str = Query("", description="Speaker ID for multi-speaker models"),
    language_id: str = Query("", description="Language ID for multi-language models"),
    style_wav: str = Query("", description="Path to style wav or JSON dict for GST")
):
    """
    Text-to-speech synthesis using the dynamically selected model.
    """
    global synthesizer

    if synthesizer is None:
        raise HTTPException(status_code=400, detail="No active model is set. Please set a model first.")

    try:
        # Process the style_wav parameter
        style_wav = style_wav_uri_to_dict(style_wav)

        # Perform TTS synthesis
        wavs = synthesizer.tts(
            text, speaker_name=speaker_id, language_name=language_id, style_wav=style_wav
        )

        # Save the generated audio
        out = io.BytesIO()
        synthesizer.save_wav(wavs, out)

        # Stream the audio response
        return StreamingResponse(out, media_type="audio/wav")
    except Exception as e:
        raise HTTPException(status_code=500, detail=handle_error(e))


@app.get("/locales", summary="Get Supported Locales", tags=["MaryTTS"])
def mary_tts_api_locales():
    """MaryTTS-compatible /locales endpoint"""
    return None

@app.get("/voices", summary="Get Supported Voices", tags=["MaryTTS"])
def mary_tts_api_voices():
    """MaryTTS-compatible /voices endpoint"""
    return None


@app.post("/process", summary="Process Text for MaryTTS", tags=["MaryTTS"])
async def mary_tts_process(text: str = Query(..., description="Input text to synthesize")):
    """
    Process text-to-speech for MaryTTS compatibility.
    """
    try:
        wavs = synthesizer.tts(text)
        out = io.BytesIO()
        synthesizer.save_wav(wavs, out)
        return StreamingResponse(out, media_type="audio/wav")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing text: {str(e)}")


@app.post("/tts", summary="Synthesize Speech from Text", tags=["TTS"])
def predict_speech(parsed_input: TTSInputs):

    try:
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
    except Exception as e:
        return handle_error(e)


@app.get("/studio_speakers", summary="Get Speaker Embeddings for XTTS", tags=["Info"])
def get_speakers():
    try:
        if hasattr(model, "speaker_manager") and hasattr(model.speaker_manager, "speakers"):
            return {
                speaker: {
                    "speaker_embedding": model.speaker_manager.speakers[speaker][
                        "speaker_embedding"].cpu().squeeze().half().tolist(),
                    "gpt_cond_latent": model.speaker_manager.speakers[speaker][
                        "gpt_cond_latent"].cpu().squeeze().half().tolist(),
                }
                for speaker in model.speaker_manager.speakers.keys()
            }
        else:
            return {}
    except Exception as e:
        return handle_error(e)


@app.get("/languages", summary="Get Supported Languages for XTTS", tags=["Info"])
def get_languages():
    try:
        return config.languages
    except Exception as e:
        return handle_error(e)


@app.get("/example_streaming_input", summary="Example Streaming Input", tags=["Examples"])
def example_streaming_input():
    """
    Provides an example input payload for /tts_stream.
    Attempts to load speaker data from test/default_speaker.json.
    """
    try:
        if not os.path.exists("test/default_speaker.json"):
            raise FileNotFoundError("default_speaker.json not found in test/ directory.")
        with open("test/default_speaker.json", "r") as fp:
            warmup_speaker = json.load(fp)
        logger.info("Example streaming input loaded successfully.")
        return {
            "text": "This is an example request.",
            "language": "en",
            "speaker_embedding": warmup_speaker["speaker_embedding"],
            "gpt_cond_latent": warmup_speaker["gpt_cond_latent"],
            "add_wav_header": True,
            "stream_chunk_size": 20,
        }
    except FileNotFoundError as fnf_error:
        logger.error(f"Speaker configuration file missing: {fnf_error}")
        return handle_error(fnf_error, "Speaker configuration file is missing.")
    except Exception as e:
        logger.error(f"Error loading example input: {e}")
        return handle_error(e)


@app.post("/clone_speaker")
def predict_speaker(wav_file: UploadFile):
    """Compute conditioning inputs from reference audio file."""
    try:
        temp_audio_name = next(tempfile._get_candidate_names())
        with open(temp_audio_name, "wb") as temp, torch.inference_mode():
            temp.write(io.BytesIO(wav_file.file.read()).getbuffer())
            gpt_cond_latent, speaker_embedding = model.get_conditioning_latents(
                temp_audio_name
            )
        return {
            "gpt_cond_latent": gpt_cond_latent.cpu().squeeze().half().tolist(),
            "speaker_embedding": speaker_embedding.cpu().squeeze().half().tolist(),
        }
    except Exception as e:
            return handle_error(e)


@app.post("/tts_stream", summary="Synthesize Speech from Text (Streaming)", tags=["TTS"])
def predict_streaming_endpoint(parsed_input: StreamingInputs):
    """
    Synthesize speech from text and stream the audio output in real-time.
    """
    try:
        logger.info("Processing /tts_stream request.")
        return StreamingResponse(
            predict_streaming_generator(parsed_input.model_dump()),
            media_type="audio/wav",
        )
    except ValueError as ve:
        logger.error(f"Validation error in /tts_stream: {ve}")
        return handle_error(ve, "Invalid input format.")
    except Exception as e:
        logger.error(f"Unexpected error in /tts_stream: {e}")
        return handle_error(e, "An error occurred while streaming audio.")


@app.get("/health", summary="Check Server Health", tags=["Info"])
def health():
    try:
        health_status = {
            "status": "healthy",
            "device": str(device),
            "gpu_available": torch.cuda.is_available(),
            "model_loaded": model is not None,
            "threads": torch.get_num_threads(),
        }
        logger.info("Health check successful.")
        return health_status
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return handle_error(e, "Health check failed.")


def postprocess(wav):
    """Post-process the output waveform."""
    if isinstance(wav, list):
        wav = torch.cat(wav, dim=0)
    wav = wav.clone().detach().cpu().numpy()
    wav = wav[None, : int(wav.shape[0])]
    wav = np.clip(wav, -1, 1)
    wav = (wav * 32767).astype(np.int16)
    return wav

def encode_audio_common(frame_input, encode_base64=True, sample_rate=24000, sample_width=2, channels=1):
    """Return base64 encoded audio."""
    wav_buf = io.BytesIO()
    with wave.open(wav_buf, "wb") as vfout:
        vfout.setnchannels(channels)
        vfout.setsampwidth(sample_width)
        vfout.setframerate(sample_rate)
        vfout.writeframes(frame_input)

    wav_buf.seek(0)
    if encode_base64:
        return base64.b64encode(wav_buf.getbuffer()).decode("utf-8")
    else:
        return wav_buf.read()

def handle_error(e, custom_message=None):
    """Handle and log errors."""
    error_message = custom_message if custom_message else "An error occurred"
    logger.error(f"{error_message}: {e}")
    return {"error": error_message, "details": str(e)}

def validate_env():
    try:
        num_threads = int(os.environ.get("NUM_THREADS", os.cpu_count()))
        use_cpu = os.environ.get("USE_CPU", "0")
        if use_cpu not in ["0", "1"]:
            raise ValueError("USE_CPU must be '0' (for CUDA) or '1' (for CPU)")
        logger.info(f"Environment validated. Threads: {num_threads}, CPU Usage: {use_cpu}")
        return num_threads, use_cpu
    except Exception as e:
        logger.error(f"Environment validation failed: {e}")
        raise

def style_wav_uri_to_dict(style_wav: str) -> Union[str, dict]:
    """Transform an uri style_wav, in either a string (path to wav file to be use for style transfer)
    or a dict (gst tokens/values to be use for styling)

    Args:
        style_wav (str): uri

    Returns:
        Union[str, dict]: path to file (str) or gst style (dict)
    """
    if style_wav:
        if os.path.isfile(style_wav) and style_wav.endswith(".wav"):
            return style_wav  # style_wav is a .wav file located on the server

        style_wav = json.loads(style_wav)
        return style_wav  # style_wav is a gst dictionary with {token1_id : token1_weigth, ...}
    return None

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
