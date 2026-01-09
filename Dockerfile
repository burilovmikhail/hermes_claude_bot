# Stage 1: Build stage
FROM python:3.11-slim AS builder

WORKDIR /app

# Install system dependencies for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Runtime stage
FROM python:3.11-slim

WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder /root/.local /root/.local

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY bot/ ./bot/

# Create a non-root user (optional but recommended for security)
# RUN useradd -m -u 1000 botuser && chown -R botuser:botuser /app
# USER botuser

# Run the bot
CMD ["python", "-m", "bot.main"]
