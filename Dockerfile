FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .


# Create non-root user first
RUN useradd --create-home --shell /bin/bash app

# Create logs directory and set proper permissions
RUN mkdir -p logs && \
    chown -R app:app /app && \
    chmod -R 755 /app && \
    chmod 777 logs

USER app


# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import asyncio; from src.bot import bot; asyncio.run(bot.get_me())" || exit 1

# Start command
CMD ["python", "main.py"]
