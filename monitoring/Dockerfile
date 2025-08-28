FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    bash \
    htop \
    iotop \
    procps \
    sysstat \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create logs directory
RUN mkdir -p /app/logs

# Make monitor script executable
RUN chmod +x /app/monitor.py

# Expose port
EXPOSE 8000

# Set entrypoint
CMD ["python", "monitor.py"]
