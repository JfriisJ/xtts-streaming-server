import pytest
from unittest.mock import patch, MagicMock
from ..task_handlers.speaker_task import process_speaker_task

@patch("task_handlers.speaker_task.generate_embeddings", return_value={"mock": "data"})
def test_process_speaker_task(mock_generate_embeddings):
    task = {
        "Type": "clone_speaker",
        "SpeakerName": "TestSpeaker",
        "AudioFileBase64": "mock_base64_audio",
    }
    redis_mock = MagicMock()
    with patch("redis.StrictRedis", return_value=redis_mock):
        process_speaker_task(task)

    redis_mock.set.assert_called_once_with("cloned_speaker:TestSpeaker", '{"mock": "data"}')
