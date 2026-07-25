# Use the official Python 3.11 slim image
FROM python:3.11-slim

# Install necessary system dependencies (like C++ build tools for annoying packages)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install CPU-only PyTorch first to prevent massive CUDA binaries which was of around 5 gb
RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# download 587MB spaCy model directly into the Docker image so it never has to download at runtime (allows offline use)
RUN pip install --no-cache-dir https://github.com/explosion/spacy-models/releases/download/en_core_web_lg-3.7.1/en_core_web_lg-3.7.1-py3-none-any.whl

# Copy the rest of the application
COPY . .

# Expose both the FastAPI port and the Streamlit port
EXPOSE 8000
EXPOSE 8501
