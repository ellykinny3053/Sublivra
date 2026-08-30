FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system build dependencies, FFmpeg, and PostgreSQL headers
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    gcc \
    python3-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip, setuptools, and wheel
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Install Python packages
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy source files
COPY . /app/

WORKDIR /app/backend

ENV PORT=8000
EXPOSE 8000

# Collect static files, run migrations, and start Gunicorn server
CMD ["sh", "-c", "python manage.py collectstatic --no-input && python manage.py migrate && gunicorn sublivra.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --threads 2 --timeout 120"]
