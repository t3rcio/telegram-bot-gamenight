# 1. Usamos a imagem oficial do UV para pegar o binário
FROM ghcr.io/astral-sh/uv:latest AS uv_bin

# 2. Imagem base minimalista do Python
FROM python:3.11-slim

ENV PYTHONTONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copia o executável do UV da primeira etapa
COPY --from=uv_bin /uv /bin/uv
COPY pyproject.toml uv.lock* .env ./
RUN set -o allexport; source .env; set +o allexport
COPY .env .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project

COPY . .

CMD ["uv", "run", "python", "main.py"]