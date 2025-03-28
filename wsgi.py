# wsgi.py - WSGI entry point for the VAST Configuration Advisor application
# This file is used by Gunicorn to serve the Flask application

import os
import sys

# Add the current directory to the Python path to ensure app.py can be found
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the Flask application instance from app.py
from app import app as application

# For compatibility with both Gunicorn and direct Python execution
app = application

# This allows the file to be run directly for development/testing
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5060))
    app.run(host='0.0.0.0', port=port)
