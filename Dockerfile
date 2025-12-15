FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install python-valve requests

# Copy the script
COPY sentinel.py .

# Run the script unbuffered so logs show up in Docker instantly
CMD ["python", "-u", "sentinel.py"]