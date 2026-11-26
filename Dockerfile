FROM python:3.12-slim

# uv installs the exact dependency versions from uv.lock
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /bin/uv

WORKDIR /app

# Dependencies first: this layer is cached until pyproject.toml or uv.lock change
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-cache

COPY server.py ./
COPY data ./data

# Do not run as root
RUN useradd --create-home app
USER app

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["python", "server.py"]
