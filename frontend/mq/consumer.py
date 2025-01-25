import redis
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

class RedisConsumer(ConsumerInterface):
    def __init__(self, host="localhost", port=6379, db=0):
        self.redis_client = redis.StrictRedis(host=host, port=port, db=db)

    def consume_message(self, queue_name="audio_tasks"):
        task_json = self.redis_client.lpop(queue_name)
        if task_json:
            return json.loads(task_json)
        return None