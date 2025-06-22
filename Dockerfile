# Use a Python base image
FROM python:3.12-slim-bookworm

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Copy requirements file and install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire Django project
COPY . /app/

# Expose the port Django will run on
EXPOSE 8000

# Command to run the Django development server (or Gunicorn in production)
# This will be overridden by docker-compose, but useful for direct docker run
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]