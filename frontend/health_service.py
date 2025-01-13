import logging
import os

import requests

XTTS_SERVER_API = os.getenv("XTTS_SERVER_API", "http://localhost:8000")
CONVERTER_API = os.getenv("CONVERTER_API", "http://localhost:5000")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def check_service_health():
    services = {
        "Converter Service": CONVERTER_API,
        "Xtts Service": XTTS_SERVER_API,
    }

    status = {}
    for service_name, url in services.items():
        try:
            response = requests.get(url + "/health", timeout=10)
            response_data = response.json()
            if response.status_code == 200 and response_data.get("status") == "healthy":
                status[service_name] = {"status": "Connected"}
            else:
                error_message = response_data.get("error", "Unknown Error")
                status[service_name] = {"status": "Disconnected", "error": error_message}
        except requests.exceptions.RequestException as e:
            status[service_name] = {"status": "Disconnected", "error": str(e)}
    return status

