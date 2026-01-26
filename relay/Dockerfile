FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY saturn_relay.py .

ENV PORT=8888
EXPOSE 8888

CMD ["python", "saturn_relay.py"]
