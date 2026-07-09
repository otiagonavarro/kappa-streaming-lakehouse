FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
COPY src/ ./src/

RUN pip install --no-cache-dir -e .

ENV PYTHONPATH=/app/src

ENTRYPOINT ["simulator"]
CMD ["--rate", "10"]
