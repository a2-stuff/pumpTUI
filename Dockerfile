FROM python:3.12-slim

# Install runtime and build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libssl-dev \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
# Using --no-cache-dir to keep image slim
RUN pip install --no-cache-dir \
    textual>=0.86.0 \
    rich>=13.7.0 \
    motor \
    pymongo \
    websockets \
    httpx \
    psutil \
    cryptography \
    python-dotenv \
    Pillow \
    solana \
    solders

# Copy application code
COPY . /app

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV COLORTERM=truecolor

# Set the entrypoint
ENTRYPOINT ["python3", "-m", "pump_tui.main"]
