from abc import ABC, abstractmethod
from typing import Any, Dict
import redis
import json


class ProducerInterface(ABC):
    @abstractmethod
    def send_message(self, task: Dict[str, Any], queue_name: str) -> None:
        """
        Send a task to the queue.

        :param task: The task data to enqueue.
        :param queue_name: The name of the queue.
        """
        pass

class RedisProducer(ProducerInterface):
    def __init__(self, host="localhost", port=6379, db=0):
        self.redis_client = redis.StrictRedis(host=host, port=port, db=db)

    def send_message(self, task, queue_name="audio_tasks"):
        task_json = json.dumps(task)
        self.redis_client.rpush(queue_name, task_json)