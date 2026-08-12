FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY app /app/app
COPY salesforce /app/salesforce

RUN pip install --no-cache-dir .

ENTRYPOINT ["python", "-m", "app.entrypoint"]

