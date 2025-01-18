import base64
import io
import os
import wave
import torch
import numpy as np
import logging
import requests
from requests import RequestException
from typing import Union

logger = logging.getLogger(__name__)

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
