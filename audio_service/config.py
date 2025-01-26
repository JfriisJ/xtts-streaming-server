import os

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB_STATUS = 0
REDIS_DB_HEALTH = 1
REDIS_DB_TASK = 2
REDIS_DB_RESULT = 3
REDIS_DB_DATA_MODEL = 4
SERVICE_NAME = os.getenv("SERVICE_NAME", "audio")
HEALTH_CHECK_CHANNEL = "health_check"
HEALTH_STATUS_CHANNEL = "health_status"
TASK_QUEUES = ["audio_tasks", "speaker_tasks", "text_tasks","generate_tts_tasks","tts_results"]
RESULT_QUEUE = "audio_results"
# Redis Configuration





