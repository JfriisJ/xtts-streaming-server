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
try:
    with open("tts_convert_format.json", "r") as schema_file:
        converter_schema = json.load(schema_file)

except json.JSONDecodeError as e:
    logger.error(f"Error loading JSON schema: {e}")
    raise

schema_registry = {
    "converter": converter_schema
}

def validate_task(task):
    """
    Validate a task against the appropriate schema based on its type.
    """
    try:
        # Determine the task type
        task_type = task.get("type")
        if not task_type:
            logger.error("Task type is missing or invalid. Cannot validate the task.")
            return False

        # Get the schema for the task type
        schema = schema_registry.get(task_type)
        if not schema:
            raise ValueError(f"No schema defined for task type: {task_type}")

        # Validate the task against the schema
        validate(instance=task, schema=schema)
        return True
    except ValidationError as e:
        logger.error(f"Task validation failed for type '{task_type}': {e.message}")
    except Exception as e:
        logger.error(f"Error during task validation: {e}")
    return False


def push_to_queue(task, queue_name="audio_tasks"):
    try:
        if not validate_task(task):
            logger.error(f"Task validation failed. Task not added to queue: {task}")
            return
        task_json = json.dumps(task)
        redis_client.rpush(queue_name, task_json)
        logger.info(f"Task added to queue {queue_name}: {task_json}")
    except redis.ConnectionError as e:
        logger.error(f"Redis connection error: {e}")


def validate_and_push_tasks(tasks, queue_name="audio_tasks"):
    for task in tasks:
        if validate_task(task):
            push_to_queue(task, queue_name)
        else:
            logger.warning(f"Task skipped due to validation failure: {task}")