# Dockerfile
FROM python:3.13-slim
WORKDIR /app
# Copy & install dependencies first
# (leverages Docker layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Copy application code
COPY . .
# Expose port Flask/Gunicorn listens on
EXPOSE 5000
# Production: run with Gunicorn (NOT app.run)
CMD ["gunicorn", "--bind", "0.0.0.0:5000","--workers", "4", "app:app"]