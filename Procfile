# Simple Procfile for DigitalOcean App Platform
# Using the exact format recommended in DigitalOcean documentation
# Addressing the Gunicorn temp directory issue in Docker environments
web: gunicorn --worker-tmp-dir /dev/shm wsgi:application
