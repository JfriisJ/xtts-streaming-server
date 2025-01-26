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
    "tts_generate": tts_generate_schema
}

# Task validation
def validate_task(task):
    """
    Validate a task against the appropriate schema based on its type.
    """
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
    try:
        validate(instance=task, schema=schema)
        return True
    except ValidationError as e:
        logger.error(f"Task validation failed for type '{task_type}': {e.message}")
        return False

