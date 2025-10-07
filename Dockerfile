FROM python:3.11-slim

WORKDIR /srv

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 10000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "10000"]
