FROM --platform=linux/amd64 python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

RUN python -m app.grpc.generator

EXPOSE 8080 50051

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
