FROM python:3.9-slim

WORKDIR /app

# Copy application files
COPY text_to_speech.py requirements.txt ./

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port for the application
EXPOSE 8003

# Run the application
CMD ["python", "text_to_speech.py"]
