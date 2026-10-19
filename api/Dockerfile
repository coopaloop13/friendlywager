FROM python:3.12-slim
ARG INSTALL_DEV=0
WORKDIR /app
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir -e . && \
    if [ "$INSTALL_DEV" = "1" ]; then pip install --no-cache-dir -e ".[dev]"; fi
COPY . .
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
