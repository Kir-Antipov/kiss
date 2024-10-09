# syntax=docker/dockerfile:1

ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION}-alpine AS base

# Prevents Python from writing pyc files.
ENV PYTHONDONTWRITEBYTECODE=1

# Keeps Python from buffering stdout and stderr to avoid situations where
# the application crashes without emitting any logs due to buffering.
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Download dependencies as a separate step to take advantage of Docker's caching.
# Leverage a cache mount to /root/.cache/pip to speed up subsequent builds.
# Leverage a bind mount to requirements.txt to avoid having to copy them into
# into this layer.
RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=bind,source=requirements.txt,target=requirements.txt \
    python -m pip install -r requirements.txt

# Copy the source code into the container.
COPY ./src/telebot/ .

# Expose the ports that the application listens on.
EXPOSE 80
EXPOSE 8080

# Run the application.
# Note: we hardcode the ports so we know what needs to be exposed.
ENTRYPOINT [ \
    "/usr/local/bin/python", ".", \
    "-c", "/data/config.json", "-d", "/data/db.sqlite3", \
    "--api-address", "", "--api-port", "80", \
    "--webhook-address", "", "--webhook-port", "8080" \
]
