import logging
import os

import requests

XTTS_SERVER_API = os.getenv("XTTS_SERVER_API", "http://localhost:8000")
CONVERTER_API = os.getenv("CONVERTER_API", "http://localhost:5000")
TEXT_SERVICE_API = os.getenv("TEXT_SERVICE_API", "http://localhost:8001")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def check_service_health():
    """
    Check the health of multiple services.

    :return: A dictionary with service names as keys and their health status as values.
    """
    services = {
        "Text Service": TEXT_SERVICE_API,
        "Converter Service": CONVERTER_API,
        "Xtts Service": XTTS_SERVER_API,
    }

    status = {}
    for service_name, url in services.items():
        try:
            response = requests.get(url + "/health", timeout=10)
            # Handle non-JSON responses
            try:
                response_data = response.json()
                logger.debug(f"Response from {service_name}: {response_data}")
                if response.status_code == 200 and response_data.get("status") == "healthy":
                    status[service_name] = {"status": "Connected"}
                else:
                    error_message = response_data.get("error", "Unknown Error")
                    status[service_name] = {"status": "Disconnected", "error": error_message}
            except ValueError:  # JSON decoding failed
                logger.warning(f"Service {service_name} returned invalid JSON.")
                status[service_name] = {"status": "Disconnected", "error": "Invalid JSON response"}
        except requests.exceptions.RequestException as e:
            logger.warning(f"Service {service_name} health check failed: {e}")
            status[service_name] = {"status": "Disconnected", "error": str(e)}
    return status
