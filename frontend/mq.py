import json
import logging
import redis
from jsonschema import validate, ValidationError

# Redis client
redis_client = redis.StrictRedis(host='localhost', port=6379, db=0)

# Logging setup
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

# Load schema for task validation
with open("mq_format.json", "r") as schema_file:
    task_schema = json.load(schema_file)


def validate_task(task):
    """
    Validate the task against the JSON schema.
    """
    try:
        validate(instance=task, schema=task_schema)
        return True
    except ValidationError as e:
        logger.error(f"Task validation failed: {e.message}")
        return False


def push_to_queue(task, queue_name="audio_tasks"):
    """
    Push a task to the Redis queue.
    """
    task_json = json.dumps(task)
    redis_client.rpush(queue_name, task_json)
    logger.info(f"Task added to queue {queue_name}: {task_json}")
