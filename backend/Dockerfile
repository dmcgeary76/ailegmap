FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# k12_ai.db lives in /app; mount a volume there to persist it.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
