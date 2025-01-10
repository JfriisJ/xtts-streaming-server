# Use a lightweight Python image
FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /app

# Copy application files
COPY text_to_speech.py requirements.txt ./

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Expose the application port
EXPOSE 8003

# Run the FastAPI application with Uvicorn
CMD ["uvicorn", "text_to_speech:app", "--host", "0.0.0.0", "--port", "8003"]
