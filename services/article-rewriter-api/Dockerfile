FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Create necessary directories
RUN mkdir -p logs/memory_pipeline generated temp

# Expose port
EXPOSE 8085

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8085"]