FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl && \
    rm -rf /var/lib/apt/lists/*

# Set NLTK data directory environment variable
ENV NLTK_DATA=/usr/share/nltk_data

# Download NLTK data during build
RUN python -m pip install --no-cache-dir nltk && \
    python -m nltk.downloader -d /usr/share/nltk_data punkt

# Copy application files
COPY frontend.py requirements.txt audio_service.py text_service.py health_service.py ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port for the application
EXPOSE 3009

# Run the application
CMD ["python", "frontend.py"]
