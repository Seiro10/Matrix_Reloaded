FROM python:3.10-slim

WORKDIR /app

ENV PYTHONPATH=/app:$PYTHONPATH

# Install curl for healthcheck
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . /app

# Create necessary directories
RUN mkdir -p /app/logs /app/temp /app/generated

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8083

# Expose port
EXPOSE 8083

# Run the application
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8083"]