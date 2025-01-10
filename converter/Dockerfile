FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install required system packages
RUN apt-get update && apt-get install -y \
    libreoffice \
    pandoc \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy application files
COPY converter.py requirements.txt ./

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the uploads and outputs directories
VOLUME /app/uploads
VOLUME /app/outputs

# Expose the port for Flask
EXPOSE 5000

# Run the application
CMD ["python", "converter.py"]
