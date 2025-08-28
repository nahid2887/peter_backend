# Use official Python image as base
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y build-essential libpq-dev && \
    rm -rf /var/lib/apt/lists/*


# Install pip requirements
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt


# Copy project files
COPY core/ ./core/
COPY account/ ./account/
COPY calender/ ./calender/
COPY chat/ ./chat/
COPY event/ ./event/
COPY media/ ./media/
COPY manage.py ./


# Copy .env file
COPY .env .env

# Collect static files (if needed)
# RUN python manage.py collectstatic --noinput

# Expose port (Django default)
EXPOSE 8000

# Start server
CMD ["gunicorn", "core.wsgi:application", "--bind", "0.0.0.0:8000"]
