#!/bin/bash

# Script to activate the virtual environment and install dependencies

# Activate the virtual environment
source venv/bin/activate

# Install dependencies if requirements.txt exists
if [ -f requirements.txt ]; then
    echo "Installing dependencies from requirements.txt..."
    pip install -r requirements.txt
else
    echo "No requirements.txt found."
fi

# Display Python version and installed packages
echo "Python version:"
python --version
echo ""
echo "Installed packages:"
pip list

echo ""
echo "Virtual environment activated. Use 'deactivate' to exit."
