from abc import abstractmethod, ABC
import json


class ConsumerInterface(ABC):
    @abstractmethod
    def consume_message(self, queue_name: str) -> None:
        """
        Consume a task from the queue and process it.

        :param queue_name: The name of the queue.
        """
        pass
