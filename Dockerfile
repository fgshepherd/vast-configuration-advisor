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

# Make port 5060 available to the world outside this container
# Note: DigitalOcean App Platform typically expects apps to listen on 8080 by default,
# but we're using 5060 to avoid conflicts with port 5000 and 5050 as per our project standards
EXPOSE 5060

# Define environment variables (optional, can be set in DO)
# ENV FLASK_ENV=production

# Run app.py when the container launches using Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5060", "app:app"]
