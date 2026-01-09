# Use Python 3.11 slim image
FROM python:3.11-slim

# Install system dependencies (including curl and ca-certificates for uv installer)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Download the latest uv installer
ADD https://astral.sh/uv/install.sh /uv-installer.sh

# Run the uv installer then remove it
RUN sh /uv-installer.sh && rm /uv-installer.sh

# Add uv to PATH
ENV PATH="/root/.cargo/bin:${PATH}"

# Install Claude Code CLI
RUN curl -fsSL https://raw.githubusercontent.com/anthropics/claude-code/main/install.sh | sh

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
# Note: Build context is project root, so we reference worker/requirements.txt
COPY worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy worker code
COPY worker/ .

# Copy ADW scripts from project root
COPY adws /app/adws

# Create workspace directory
RUN mkdir -p /workspace

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run worker
CMD ["python", "main.py"]
