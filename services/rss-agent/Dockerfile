FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY config/ ./config/
COPY core/ ./core/
COPY models/ ./models/
COPY scrapers/ ./scrapers/
COPY services/ ./services/
COPY main.py .

RUN useradd -m -u 1000 rssuser

RUN mkdir -p /app/data && chown -R rssuser:rssuser /app

# Set Python path
ENV PYTHONPATH=/app

USER rssuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8086/health || exit 1

# Default command
CMD ["python", "main.py"]