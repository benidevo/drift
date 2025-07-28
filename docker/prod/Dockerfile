FROM python:3.12-slim-bookworm as builder

WORKDIR /app

ENV POETRY_HOME=/opt/poetry
ENV POETRY_VIRTUALENVS_IN_PROJECT=true
ENV PATH="$POETRY_HOME/bin:$PATH"
RUN pip install poetry

COPY pyproject.toml poetry.lock* ./

RUN poetry install --no-interaction --no-ansi --without dev

RUN poetry export -f requirements.txt --output requirements.txt --without-hashes

FROM python:3.12-slim-bookworm

RUN useradd -m -u 1000 drift

WORKDIR /app

COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && rm requirements.txt

COPY --chown=drift:drift src/ ./src/

USER drift

ENV PYTHONPATH=/app/src

ENTRYPOINT ["python", "-m", "drift"]
