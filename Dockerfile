FROM python:3.11-slim

# Prevent Python from writing .pyc files & buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system audio utilities & PostgreSQL libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Set working directory to backend for Django commands
WORKDIR /app/backend

# Collect static files
RUN python manage.py collectstatic --no-input

# Set port and start Gunicorn server
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate && gunicorn sublivra.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --threads 2 --timeout 120"]
