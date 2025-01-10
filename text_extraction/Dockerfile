# Use a lightweight Python base image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Copy application files
COPY text_extraction.py requirements.txt ./

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Expose the application port
EXPOSE 8001

# Run the FastAPI application
CMD ["uvicorn", "text_extraction:app", "--host", "0.0.0.0", "--port", "8001"]
