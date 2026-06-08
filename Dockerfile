FROM python:3.11-slim AS backend
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY eval ./eval
COPY pytest.ini README.md ./
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
