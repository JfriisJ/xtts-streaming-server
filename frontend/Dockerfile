FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Install necessary system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    libsndfile1-dev \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables for logging and NLTK data
ENV PYTHONUNBUFFERED=1
ENV NLTK_DATA=/usr/share/nltk_data

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Download NLTK data required for the application
RUN python -m nltk.downloader -d /usr/share/nltk_data punkt

# Copy application files into the container
COPY audio_service.py frontend.py health_service.py text_service.py ./

# Expose the application port
EXPOSE 3009

# Set the default command to run the application
CMD ["python", "frontend.py"]
