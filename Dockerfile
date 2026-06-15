FROM python:3.11-slim

WORKDIR /app

# Install native system dependencies if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
RUN pip install --no-cache-dir requests openai

# Copy application source
COPY . .

RUN mkdir -p /app/data

CMD ["python", "main.py"]