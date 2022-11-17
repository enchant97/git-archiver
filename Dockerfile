ARG PYTHON_VERSION=3.10

FROM python:${PYTHON_VERSION}-alpine

    WORKDIR /app

    RUN apk add --no-cache git

    COPY requirements.txt .

    RUN --mount=type=cache,target=/root/.cache pip install -r requirements.txt

    COPY git_archiver git_archiver
    COPY LICENSE.txt .

    ENTRYPOINT ["python", "-m", "git_archiver"]
    CMD ["--help"]
