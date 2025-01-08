# Use a lightweight base image
FROM python:3.10-slim

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive

# Install LibreOffice and Pandoc
RUN apt-get update && apt-get install -y \
    libreoffice \
    pandoc \
    unzip \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy application files
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Expose port
EXPOSE 5000

# Run the application
CMD ["python", "api.py"]
