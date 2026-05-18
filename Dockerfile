FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

COPY . .

HEALTHCHECK --interval=5s --timeout=3s --retries=10 \
    CMD python -c "import socket; s=socket.socket(); s.connect(('127.0.0.1', 8989)); s.close()"

CMD ["nb", "run"]
