FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-devel

WORKDIR /app

# Install required system packages
RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    sox libsox-fmt-all curl wget gcc git git-lfs build-essential libaio-dev \
    libsndfile1 ssh ffmpeg && \
    apt-get clean && apt-get -y autoremove

# Copy requirements.txt
COPY requirements.txt .

# Install dependencies
RUN python -m pip install --use-deprecated=legacy-resolver --timeout 120 -r requirements.txt && \
    python -m pip cache purge

# Copy the application code
COPY . .

# GPU Compatibility: Set to 1 for older GPUs
ENV NVIDIA_DISABLE_REQUIRE=0

# Set number of threads for PyTorch
ENV NUM_THREADS=2

# Expose the application port
EXPOSE 80

# Run the application using Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]
