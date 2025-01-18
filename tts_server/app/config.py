import logging
import os
from pydantic import BaseModel
from typing import Optional
from pathlib import Path
import torch
from TTS.TTS.utils.manage import ModelManager

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

