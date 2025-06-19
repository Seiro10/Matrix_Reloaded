FROM python:3.10-slim

WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY ./src /app

# Create necessary directories
RUN mkdir -p /app/logs /app/temp

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8084

# Expose port
EXPOSE 8084

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8084"]
