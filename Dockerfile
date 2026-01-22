FROM python:3.12-alpine

# Install build dependencies for Python packages with C extensions
RUN apk add --no-cache \
    gcc \
    musl-dev \
    libffi-dev \
    openssl-dev \
    cargo \
    git

# Set working directory
WORKDIR /app

# Copy requirements or install dependencies directly
# Install Python dependencies
RUN pip install --no-cache-dir \
    textual \
    motor \
    pymongo \
    websockets \
    httpx \
    psutil \
    rich \
    cryptography \
    python-dotenv \
    Pillow

# Remove build dependencies to reduce image size (keep runtime deps)
RUN apk del gcc musl-dev cargo

# Copy application code
COPY . /app

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Expose any necessary ports (if needed for future features)
# EXPOSE 8000

# Set the entrypoint
ENTRYPOINT ["python3", "-m", "pump_tui.main"]
