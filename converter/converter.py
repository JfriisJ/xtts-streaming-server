import json

from fastapi import FastAPI, UploadFile, HTTPException
import os
import logging
import redis
import threading
import signal
from converters.md_to_json import md_to_json
from mq.consumer import RedisConsumer
from mq.producer import RedisProducer
from spellcheck import process_json_content


# Setup logging
os.makedirs('/app/logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("/app/logs/converter.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="File Conversion API",
    description="Converts various document formats to structured JSON.",
    version="0.0.2",
    docs_url="/",
)

UPLOAD_FOLDER = "/app/uploads"
OUTPUT_FOLDER = "/app/outputs"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
try:
    redis_client = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=False, db=0)
    redis_health_care = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=False, db=1)

except Exception as e:
    logger.error(f"Error connecting to Redis: {e}")

producer = RedisProducer()
consumer = RedisConsumer()

# Channel definitions
HEALTH_CHECK_CHANNEL = "health_check"
HEALTH_STATUS_CHANNEL = "health_status"
SERVICE_NAME = os.getenv("SERVICE_NAME", "frontend")

def listen_for_health_checks():
    """
    Listen for health check requests and respond with the service's health status.
    """
    pubsub = redis_health_care.pubsub()
    pubsub.subscribe(HEALTH_CHECK_CHANNEL)
    logger.info(f"Subscribed to channel {HEALTH_CHECK_CHANNEL} for health checks.")

    try:
        for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    health_request = json.loads(message["data"])
                    if health_request.get("action") == "health_check":
                        # Publish service status
                        health_status = {"service": SERVICE_NAME, "status": "healthy"}
                        redis_health_care.publish(HEALTH_STATUS_CHANNEL, json.dumps(health_status))
                        logger.info(f"Responded to health check: {health_status}")
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON in health check message: {message['data']} - {e}")
                except Exception as e:
                    logger.error(f"Error processing health check: {e}")
    except KeyboardInterrupt:
        logger.info("Shutting down health check listener.")
    except Exception as e:
        logger.error(f"Unexpected error in health check listener: {e}")

def shutdown_handler(signum, frame):
    """
    Handle shutdown signals gracefully.
    """
    logger.info("Received shutdown signal. Exiting.")
    exit(0)

@app.post("/convert")
async def convert(file: UploadFile):
    logger.info(f"Received file: {file.filename}")
    try:
        file_extension = os.path.splitext(file.filename)[-1].lower()
        logger.debug(f"File extension detected: {file_extension}")

        # Read the file content as bytes and decode
        content = (await file.read()).decode("utf-8")

        # Convert Markdown to JSON
        json_content = md_to_json(content)

        # Process spell checking on JSON content
        processed_content = process_json_content(json_content["Sections"])

        logger.info(f"Spell-checked content: {processed_content}")

        # Update JSON content with spell-checked data
        json_content["Sections"] = processed_content

        return json_content  # Return processed JSON content
    except Exception as e:
        logger.error(f"Error converting file {file.filename}: {e}")
        raise HTTPException(status_code=500, detail="Conversion failed.")


@app.get("/health")
def health():
    """
    health check endpoint for the API.
    """
    try:
        logger.info("health check requested.")
        return {"status": "healthy"}
    except Exception as e:
        logger.error(f"health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}


if __name__ == "__main__":
    # Signal handling for graceful shutdown
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    # Start health check listener in a separate thread
    listener_thread = threading.Thread(target=listen_for_health_checks, daemon=True)
    listener_thread.start()

    # Keep the main thread alive
    while True:
        signal.pause()