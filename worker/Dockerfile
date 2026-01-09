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

# Install Claude Code CLI (official method)
RUN curl -fsSL https://claude.ai/install.sh | bash

# Add Claude Code to PATH and set CLAUDE_CODE_PATH
ENV PATH="/root/.local/bin:${PATH}"
ENV CLAUDE_CODE_PATH="/root/.local/bin/claude"

# Create Claude Code config directory
RUN mkdir -p /root/.config/claude-code

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

# Copy and set up entrypoint script
COPY worker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Create workspace directory
RUN mkdir -p /workspace

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Use entrypoint script to configure Claude Code at runtime
ENTRYPOINT ["/entrypoint.sh"]
