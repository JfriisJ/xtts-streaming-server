import pytest
from unittest.mock import patch, MagicMock
from ..task_listener import listen_to_queues

def test_listen_to_queues():
    mock_redis = MagicMock()
    mock_redis.blpop.side_effect = [
        ("audio_tasks", '{"task_id": "1234", "text": "hello"}'),
        KeyboardInterrupt,  # Simulate shutdown
    ]
    with patch("redis.StrictRedis", return_value=mock_redis):
        with patch("task_handlers.audio_task.process_audio_task") as mock_process_audio_task:
            listen_to_queues(mock_redis, ["audio_tasks"])
            mock_process_audio_task.assert_called_once()
