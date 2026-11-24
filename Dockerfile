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
EXPOSE 5000
CMD ["python", "-m", "flask", "--app", "app:create_app", "--no-debug", "run", "--host=0.0.0.0", "--port=5000", "--no-reload"]
