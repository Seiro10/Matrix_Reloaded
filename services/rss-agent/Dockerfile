FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for Playwright and image processing
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    wget \
    libnss3 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxkbcommon0 \
    libgtk-3-0 \
    libgbm1 \
    libasound2 \
    libxss1 \
    libgconf-2-4 \
    libxtst6 \
    libxrandr2 \
    libasound2 \
    libpangocairo-1.0-0 \
    libatk1.0-0 \
    libcairo-gobject2 \
    libgtk-3-0 \
    libgdk-pixbuf2.0-0 \
    libavif-dev \
    libheif-dev \
    && rm -rf /var/lib/apt/lists/*

# Create user first
RUN useradd -m -u 1000 rssuser

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

# Create directories and set permissions
RUN mkdir -p /app/data && chown -R rssuser:rssuser /app
RUN mkdir -p /home/rssuser/.cache && chown -R rssuser:rssuser /home/rssuser

# Switch to user and install Playwright browsers
USER rssuser

# Install Playwright browsers as the rssuser
RUN python -m playwright install chromium

# Set Python path
ENV PYTHONPATH=/app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8086/health || exit 1

# Default command
CMD ["python", "main.py"]