FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY . .

RUN mkdir -p /data/uploads/csv /data/uploads/images /data/data

ENV BACKTESTING_DATA_DIR=/data

EXPOSE 8080

CMD ["gunicorn", "-b", "0.0.0.0:8080", "-w", "2", "--timeout", "120", "app:app"]
