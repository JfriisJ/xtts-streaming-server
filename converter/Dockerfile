# Use a lightweight Python image
FROM python:3.9-slim

# Install system dependencies for pandoc and libreoffice
RUN apt-get update && apt-get install -y \
    curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy application files
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Create necessary directories
RUN mkdir -p /app/uploads /app/outputs /app/logs

# Expose the application port
EXPOSE 5000

# Run the FastAPI application
CMD ["uvicorn", "converter:app", "--host", "0.0.0.0", "--port", "5000"]
