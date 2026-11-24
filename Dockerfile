FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_PATH=/data/tasks.sqlite3

WORKDIR /app
COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

RUN groupadd --gid 10001 taskmanager \
    && useradd --uid 10001 --gid taskmanager --no-create-home taskmanager \
    && install -d -o taskmanager -g taskmanager /data
COPY app.py .
COPY templates/ templates/
COPY static/ static/

USER taskmanager
ARG APP_VERSION
ARG GIT_SHA
RUN python -c "import re,sys; sys.exit(0 if sys.argv[1] and re.fullmatch('[0-9a-f]{40}', sys.argv[2]) else 'Build requires APP_VERSION and the full Git SHA')" "$APP_VERSION" "$GIT_SHA"
ENV APP_VERSION=$APP_VERSION GIT_SHA=$GIT_SHA
LABEL org.opencontainers.image.version=$APP_VERSION \
      org.opencontainers.image.revision=$GIT_SHA
EXPOSE 5000
CMD ["python", "-m", "flask", "--app", "app:create_app", "--no-debug", "run", "--host=0.0.0.0", "--port=5000", "--no-reload"]
