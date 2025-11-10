FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del backend
COPY server/requirements.txt /app/server/requirements.txt
RUN pip install --no-cache-dir -r /app/server/requirements.txt

# Copiar código del backend
COPY server /app/server

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Ejecutar FastAPI con uvicorn
CMD ["uvicorn", "server.app.main:app", "--host", "0.0.0.0", "--port", "8000"]