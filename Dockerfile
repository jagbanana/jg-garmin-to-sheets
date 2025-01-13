FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

# Add gunicorn for serving the app
RUN pip install gunicorn flask

# Set environment variables
ENV PORT=8080

ENTRYPOINT ["python", "-m", "src.main"]