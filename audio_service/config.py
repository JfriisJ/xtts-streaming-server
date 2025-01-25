import os

# Redis Config
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB_TTS = 4

# Task Queues
TASK_QUEUES = ["audio_tasks", "speaker_tasks", "text_tasks"]

# Health Check Channels
HEALTH_CHECK_CHANNEL = "health_check"
HEALTH_STATUS_CHANNEL = "health_status"

# Service Info
SERVICE_NAME = os.getenv("SERVICE_NAME", "audio_service")
