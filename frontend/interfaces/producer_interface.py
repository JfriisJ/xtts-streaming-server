import json
from abc import ABC, abstractmethod
from typing import Any, Dict

import redis


class ProducerInterface(ABC):
    @abstractmethod
    def send_message(self, task: Dict[str, Any], queue_name: str) -> None:
        """
        Send a task to the queue.

        :param task: The task data to enqueue.
        :param queue_name: The name of the queue.
        """
        pass
