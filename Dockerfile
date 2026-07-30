FROM python:3.10-slim

# Install system dependencies (FFmpeg, Aria2, Git, GCC)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev musl-dev ffmpeg aria2 curl git \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Copy source code
COPY . .

# Run the bot engine
CMD ["python", "main.py"]