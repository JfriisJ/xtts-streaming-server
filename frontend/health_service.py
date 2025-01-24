import logging
import os

import requests

TTS_SERVER_API = os.getenv("TTS_SERVER_API", "http://localhost:4001")
CONVERTER_API = os.getenv("CONVERTER_API", "http://localhost:5000")


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def check_service_health():
    services = {"Converter Service": CONVERTER_API, "Xtts Service": TTS_SERVER_API}
    status = {}

    for service_name, url in services.items():
        try:
            response = requests.get(f"{url}/health", timeout=10)
            response.raise_for_status()
            status[service_name] = {"status": "Connected"}
        except requests.RequestException as e:
            logger.error(f"{service_name} health check failed: {e}")
            status[service_name] = {"status": "Disconnected", "error": str(e)}

    return status
