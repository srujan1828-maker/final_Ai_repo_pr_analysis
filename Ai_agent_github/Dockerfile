FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY models.py graph.py service.py .
COPY fixtures/ ./fixtures/

# Expose port 8000
EXPOSE 8000

# Run Uvicorn server
CMD ["uvicorn", "service:app", "--host", "0.0.0.0", "--port", "8000"]
