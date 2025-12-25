# Dockerfile for x0tta6bl4 FastAPI application

# Stage 1: Base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
# Assuming the application is in the 'src' directory
COPY ./src /app/src

# Expose the port the app runs on
EXPOSE 8080

# Run the application
# We use uvicorn to run the FastAPI app found in src/core/app.py
CMD ["uvicorn", "src.core.app:app", "--host", "0.0.0.0", "--port", "8080"]
