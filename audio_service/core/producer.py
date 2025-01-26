from abc import ABC, abstractmethod
from typing import Any, Dict
import redis
import json

from audio_service.core.mq import push_to_queue


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

class TaskProducer:
    def __init__(self, redis_client):
        self.redis_client = redis_client

    def add_audio_task(self, task):
        """
        Tilføj en audio task til køen.
        """
        push_to_queue(self.redis_client, "audio_tasks", task)

    def add_speaker_task(self, task):
        """
        Tilføj en speaker task til køen.
        """
        push_to_queue(self.redis_client, "speaker_tasks", task)

    def add_text_task(self, task):
        """
        Tilføj en text task til køen.
        """
        push_to_queue(self.redis_client, "text_tasks", task)