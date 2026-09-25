FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY main.py .

RUN mkdir -p data images

ENV PYTHONPATH=/app
ENV DB_PATH=/data/simulation.db

EXPOSE 8000

CMD ["python", "main.py", "web", "--port", "8000", "--db", "/data/simulation.db"]
