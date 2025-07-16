#!/bin/bash

# Start the Kalanjiyam Celery worker
# This script starts the Celery worker for background tasks

set -e

echo "Starting Kalanjiyam Celery worker..."

# Check if we're in a Docker container
if [ -f /.dockerenv ]; then
    echo "Running in Docker container..."
    
    # Switch to python venv and start Celery worker
    . /venv/bin/activate
    export PATH=$PATH:/venv/bin/
    
    celery -A kalanjiyam.tasks worker --loglevel=INFO
else
    echo "Running locally..."
    
    # Start Celery worker locally
    celery -A kalanjiyam.tasks worker --loglevel=INFO
fi
