FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY eval ./eval
COPY .streamlit ./.streamlit

RUN uv sync --frozen --no-dev

ENV LLM_PROVIDER=mock
EXPOSE 8501

CMD ["uv", "run", "streamlit", "run", "src/pergunteoee/app/streamlit_app.py", "--server.address=0.0.0.0", "--server.port=8501"]
