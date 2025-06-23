# Dockerfile for the casino app (main.py as entry point)
FROM python:3.11-slim

WORKDIR /app

COPY . /app

# Install dependencies if requirements.txt exists
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi

CMD ["python", "main.py"]
