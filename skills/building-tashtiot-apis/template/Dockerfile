# BASE_IMAGE: the approved Python 3.12 image in JFrog Artifactory (CI passes it as a build arg).
ARG BASE_IMAGE
FROM ${BASE_IMAGE}

# Release version shown in Swagger; CI passes the git tag: --build-arg APP_VERSION=<tag>.
ARG APP_VERSION=v0.0.0
ENV APP_VERSION=${APP_VERSION}
ENV UV_LINK_MODE=copy

RUN pip install --upgrade pip uv

WORKDIR /app
# Lock + manifest first, so the dependency layer is cached until they change.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev

COPY app ./app

# --no-sync: run from the .venv built above, no network at container start.
# One uvicorn process per pod; scale with replicas.
CMD ["uv", "run", "--no-sync", "-m", "app.main", "--host", "0.0.0.0", "--port", "5000"]
