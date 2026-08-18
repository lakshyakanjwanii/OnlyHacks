# Use official Python slim image for a lightweight footprint
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies if required (e.g. for psycopg2 or httpx)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Expose port (Render sets the PORT environment variable)
EXPOSE 8000

# Start the FastAPI application
CMD ["uvicorn", "src.server:app", "--host", "0.0.0.0", "--port", "8000"]
