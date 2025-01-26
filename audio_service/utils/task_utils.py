import json

from jsonschema import validate, ValidationError
from audio_service.utils.logging_utils import setup_logger


logger = setup_logger(name="TaskUtils")


# Load schema for task validation
try:
    with open("schema/tts_format.json", "r") as schema_file:
        tts_format_schema = json.load(schema_file)
    with open("schema/tts_generate.json", "r") as schema_file:
        tts_generate_schema = json.load(schema_file)
except json.JSONDecodeError as e:
    logger.error(f"Error loading JSON schema: {e}")
    raise

schema_registry = {
    "tts_generate": tts_generate_schema,
    "tts_format": tts_format_schema
}


def get_schema_from_redis(task_type):
    """
    Fetch a schema from Redis by task type.

    :param task_type: Type of the task (e.g., 'tts_generate').
    :return: Schema JSON object or None if not found.
    """
    from audio_service.utils.redis_utils import redis_client_db_data_model
    try:
        schema_json = redis_client_db_data_model.get(f"schema:{task_type}")
        if schema_json:
            return json.loads(schema_json)
        if not schema_json:
            # Fallback to schema_registry if Redis doesn't have the schema
            schema = schema_registry.get(task_type)
            if not schema:
                logger.error(f"No schema defined for task type: {task_type}")
                return False
            redis_client_db_data_model.set(f"schema:{task_type}", json.dumps(schema))
            return json.loads(schema_json)

        logger.warning(f"Schema for task type '{task_type}' not found in Redis.")
        return None
    except Exception as e:
        logger.error(f"Error fetching schema for task type '{task_type}' from Redis: {e}")
        return None

def validate_task(task):
    """
    Validate a task against the appropriate schema based on its type.
    """
    # Determine the task type
    task_type = task.get("task_type")
    if not task_type:
        logger.error("Task type is missing or invalid. Cannot validate the task.")
        return False

    # Try fetching the schema from Redis
    schema = get_schema_from_redis(task_type)
    if not schema:
        return False
    # Validate the task against the schema
    try:
        validate(instance=task, schema=schema)
        return True
    except ValidationError as e:
        logger.error(f"Task validation failed for type '{task_type}': {e.message}")
        return False
