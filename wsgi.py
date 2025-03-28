# wsgi.py - Simple WSGI entry point for DigitalOcean App Platform
# This file is intentionally kept minimal to avoid deployment issues

from app import app as application

# This is the standard WSGI variable that Gunicorn looks for
app = application

# For direct execution during development
if __name__ == "__main__":
    import os
    port = int(os.environ.get('PORT', 8080))
    application.run(host='0.0.0.0', port=port)
