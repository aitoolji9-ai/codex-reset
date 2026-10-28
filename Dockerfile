FROM python:3.12.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 STATE_DIR=/state
WORKDIR /app
COPY cli.py reset_notifier.py transport.py ./
RUN groupadd --gid 10001 notifier && useradd --uid 10001 --gid 10001 --no-create-home notifier && mkdir /state && chown 10001:10001 /state && chmod 700 /state
USER 10001:10001
VOLUME ["/state"]
STOPSIGNAL SIGTERM
ENTRYPOINT ["python", "cli.py"]
