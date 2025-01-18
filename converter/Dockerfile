# Use a lightweight Python image
FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy application files
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt
# Expose the application port
EXPOSE 5000

# Run the FastAPI application
CMD ["uvicorn", "converter:app", "--host", "0.0.0.0", "--port", "5000"]
