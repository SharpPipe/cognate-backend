FROM python:3.10.1-slim-buster
ENV PYTHONUNBUFFERED=1
WORKDIR /usr/src/app
COPY requirements.txt ./
EXPOSE 8081
RUN apt update && apt install -y graphviz cron && rm -rf /var/lib/apt/lists/*
RUN pip3 install -r requirements.txt
COPY db-backup-cron /etc/cron.d/db-backup-cron
RUN chmod 0644 /etc/cron.d/db-backup-cron && crontab /etc/cron.d/db-backup-cron
