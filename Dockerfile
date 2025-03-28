# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the dependencies file to the working directory
COPY requirements.txt .

# Install any needed dependencies specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code to the working directory
COPY . .

# Make port 8080 available to the world outside this container
# Note: DigitalOcean App Platform expects apps to listen on 8080 by default
EXPOSE 8080

# Define environment variables for the application
ENV FLASK_ENV=production
ENV PORT=8080
ENV PYTHONUNBUFFERED=1

# Run the application using Gunicorn with wsgi.py
# Using the worker-tmp-dir parameter to fix the Docker temp directory issue
# Using wsgi:application to match our current configuration
CMD ["gunicorn", "--worker-tmp-dir", "/dev/shm", "--log-file=-", "--workers=2", "--bind=0.0.0.0:8080", "wsgi:application"]
