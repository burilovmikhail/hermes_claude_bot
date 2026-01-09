# Use Python 3.11 slim image
FROM python:3.11-slim

# Install system dependencies (including curl and ca-certificates for uv installer)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install GitHub CLI
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
    && apt-get update \
    && apt-get install -y gh \
    && rm -rf /var/lib/apt/lists/*

# Download the latest uv installer
ADD https://astral.sh/uv/install.sh /uv-installer.sh

# Run the uv installer then remove it
RUN sh /uv-installer.sh && rm /uv-installer.sh

# Add uv to PATH
ENV PATH="/root/.cargo/bin:${PATH}"

# Create a non-root user to run the worker
RUN useradd -m -u 1000 -s /bin/bash worker && \
    mkdir -p /home/worker/.config/claude-code && \
    mkdir -p /workspace && \
    chown -R worker:worker /home/worker /workspace

# Switch to worker user to install Claude Code
USER worker

# Install Claude Code CLI as worker user (official method)
RUN curl -fsSL https://claude.ai/install.sh | bash

# Add Claude Code to PATH and set CLAUDE_CODE_PATH
ENV PATH="/home/worker/.local/bin:${PATH}"
ENV CLAUDE_CODE_PATH="/home/worker/.local/bin/claude"

# Switch back to root for remaining setup
USER root

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

# Change ownership of app directory to worker user
RUN chown -R worker:worker /app

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV HOME=/home/worker

# Switch to non-root user
USER worker

# Use entrypoint script to configure Claude Code at runtime
ENTRYPOINT ["/entrypoint.sh"]
