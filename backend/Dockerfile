FROM mcr.microsoft.com/playwright/python:v1.58.0-noble
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt
COPY . /app
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
