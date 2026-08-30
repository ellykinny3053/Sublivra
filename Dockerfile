FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install minimal ffmpeg and runtime libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy application source
COPY . /app/

WORKDIR /app/backend

ENV PORT=8000
EXPOSE 8000

# Run collectstatic & migrate at container startup, then launch Gunicorn
CMD ["sh", "-c", "python manage.py collectstatic --no-input && python manage.py migrate && gunicorn sublivra.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --threads 2 --timeout 120"]
