# Dockerfile
FROM python:3.13-slim
WORKDIR /app
# Copy & install dependencies first
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Copy application code
COPY . .
# Expose port Flask/Gunicorn listens on
EXPOSE 5000
# Production: run with Gunicorn (NOT app.run)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "180", "app:app"]