FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.lock pyproject.toml README.md ./
RUN python -m pip install --no-cache-dir -r requirements.lock

COPY app ./app
COPY tests ./tests
COPY scripts ./scripts
COPY main.py ./main.py
RUN python -m pip install --no-cache-dir --no-deps --no-build-isolation .

RUN addgroup --system --gid 1000 vaa \
    && adduser --system --uid 1000 --ingroup vaa --home /app vaa \
    && chown -R vaa:vaa /app

USER vaa

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
