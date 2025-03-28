# Simple Procfile for DigitalOcean App Platform
# This tells DigitalOcean how to run our application using the standard format
# Updated to use wsgi.py as the entry point for better compatibility with DigitalOcean App Platform
# Explicitly specifying the application module to resolve "No application module specified" error
web: gunicorn --log-file=- --workers=2 --bind=0.0.0.0:8080 --pythonpath /app wsgi:application
