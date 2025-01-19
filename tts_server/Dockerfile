FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime


# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy application files
COPY requirements.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt


# Copy the application code
COPY /TTS main.py requirements.txt ./

# GPU Compatibility: Set to 1 for older GPUs
ENV NVIDIA_DISABLE_REQUIRE=0

# Set number of threads for PyTorch
ENV NUM_THREADS=2

# Expose the application port
EXPOSE 80

# Run the application using Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]

