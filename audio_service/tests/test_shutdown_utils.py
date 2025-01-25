import pytest
from unittest.mock import patch, MagicMock
from ..utils.shutdown_utils import shutdown_handler
import signal


def test_shutdown_handler_logs_and_exits():
    """
    Test that the shutdown handler logs the correct message and exits.
    """
    with patch("utils.shutdown_utils.logger") as mock_logger, patch("sys.exit") as mock_exit:
        shutdown_handler(signal.SIGINT, None)
        mock_logger.info.assert_called_once_with("Received shutdown signal. Exiting.")
        mock_exit.assert_called_once_with(0)
