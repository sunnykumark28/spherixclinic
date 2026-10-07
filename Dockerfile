FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    FLASK_PORT=7860 \
    FLASK_HOST=0.0.0.0 \
    USE_SSL=False

WORKDIR /app

# Install system dependencies (build-essential, curl, libgomp1 for ML libs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project
COPY . .

# Create non-root user (Hugging Face Spaces standard) with home directory
RUN useradd -m -u 1000 user && \
    chown -R user:user /app

USER user

# Hugging Face Spaces exposes port 7860 by default
EXPOSE 7860

# Run the Flask application
CMD ["python", "app.py"]
