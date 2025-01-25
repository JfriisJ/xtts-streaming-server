import pytest
from unittest.mock import patch
from audio_service.task_handlers.audio_task import process_audio_task


@pytest.fixture
def mock_redis():
    """Mock Redis instance."""
    with patch("redis.StrictRedis") as mock_redis:
        yield mock_redis


@patch("audio_service.utils.audio_utils.send_tts_job", return_value="mock_audio_base64")
def test_process_audio_task(mock_send_tts_job, mock_redis):
    """Test process_audio_task."""
    task = {
        "task_id": "1234",
        "text": "Hello world",
        "language": "en",
        "speaker_embedding": [0.1, 0.2],
        "gpt_cond_latent": [[0.3, 0.4]],
    }
    mock_redis.return_value.get.return_value = None  # Simulate empty Redis cache

    process_audio_task(task)

    mock_send_tts_job.assert_called_once_with(
        "Hello world", "en", [0.1, 0.2], [[0.3, 0.4]]
    )
