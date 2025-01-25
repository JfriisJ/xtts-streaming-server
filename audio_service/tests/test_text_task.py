import pytest
from unittest.mock import patch, MagicMock
from ..task_handlers.text_task import process_text_task


def test_process_text_task_valid_task():
    """
    Test that process_text_task logs the correct message for a valid task.
    """
    task = {
        "Type": "text_processing",
        "content": "This is a sample text.",
    }
    with patch("task_handlers.text_task.logger") as mock_logger:
        process_text_task(task)
        mock_logger.info.assert_called_once_with(f"Processing text task: {task}")


def test_process_text_task_invalid_task():
    """
    Test that process_text_task logs a warning for an invalid task type.
    """
    task = {
        "Type": "unknown_task",
        "content": "Invalid task type.",
    }
    with patch("task_handlers.text_task.logger") as mock_logger:
        process_text_task(task)
        mock_logger.warning.assert_called_once_with(f"Unhandled text task type: {task.get('Type')}")


def test_process_text_task_empty_task():
    """
    Test that process_text_task handles an empty task gracefully.
    """
    task = {}
    with patch("task_handlers.text_task.logger") as mock_logger:
        process_text_task(task)
        mock_logger.warning.assert_called_once_with(f"Invalid or empty text task: {task}")


def test_process_text_task_missing_content():
    """
    Test that process_text_task handles a task missing required fields gracefully.
    """
    task = {"Type": "text_processing"}
    with patch("task_handlers.text_task.logger") as mock_logger:
        process_text_task(task)
        mock_logger.warning.assert_called_once_with(f"Invalid or incomplete text task: {task}")
