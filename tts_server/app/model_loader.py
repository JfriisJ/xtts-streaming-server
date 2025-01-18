from pydantic import BaseModel

from tts_server.TTS.TTS.utils.manage import ModelManager
import logging

from TTS.TTS.utils.synthesizer import Synthesizer

logger = logging.getLogger(__name__)


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
