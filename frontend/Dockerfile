FROM python:3.9-slim

WORKDIR /app

# Copy application files
COPY frontend.py requirements.txt ./

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port for the application
EXPOSE 3009

# Run the application
CMD ["python", "frontend.py"]
