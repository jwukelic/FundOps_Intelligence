FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app

# Default: run as Cloud Run service.
# Set RUN_MODE=job to run as a Cloud Run job (single execution, then exit).
CMD ["python", "-m", "app.main"]
