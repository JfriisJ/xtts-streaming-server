import logging
from typing import List
from pydantic import BaseModel, field_validator, Field
from fastapi import Body
import torch
from utils import postprocess

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
