FROM python:3.10.1-slim-buster
ENV PYTHONUNBUFFERED=1
WORKDIR /usr/src/app
COPY requirements.txt ./
EXPOSE 8000
RUN pip3 install -r requirements.txt
