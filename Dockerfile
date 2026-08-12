FROM python:3.13-slim

LABEL org.opencontainers.image.source=https://github.com/brk3/ogma
LABEL org.opencontainers.image.description="Links finished qBittorrent downloads into Plex-friendly folders"

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY link_media.py health.py watch.py migrate_leaf_names.py /app/

WORKDIR /app
USER 1000:1000
EXPOSE 8080
ENTRYPOINT ["python3", "/app/watch.py"]
