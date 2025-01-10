FROM python:3.9-slim

WORKDIR /app

# Install curl and other necessary dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl && \
    rm -rf /var/lib/apt/lists/*

# Copy application files
COPY frontend.py requirements.txt audio_service.py text_service.py ./

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port for the application
EXPOSE 3009

# Run the application
CMD ["python", "frontend.py"]
