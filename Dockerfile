FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copia e instala as dependências via wheels pré-compilados do PyPI (muito mais rápido e sem travar em apt)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código da aplicação
COPY app/ ./app
COPY .env* ./

# Cria pastas para montagem de volumes persistentes
RUN mkdir -p /app/data /app/credentials

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
