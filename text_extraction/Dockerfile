FROM python:3.9-slim

WORKDIR /app

# Copy application files
COPY text_extraction.py requirements.txt ./

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port for the Flask app
EXPOSE 8001

# Run the application
CMD ["python", "text_extraction.py"]
