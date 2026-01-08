# Use Python 3.11 slim image
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI
RUN curl -fsSL https://raw.githubusercontent.com/anthropics/claude-code/main/install.sh | sh

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy worker code
COPY . .

# Create workspace directory
RUN mkdir -p /workspace

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run worker
CMD ["python", "main.py"]
