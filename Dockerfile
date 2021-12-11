FROM python:3.10

ARG DJANGO_SUPERUSER_PASSWORD
RUN apt-get update \
    && rm -rf /var/lib/apt/lists/*

RUN addgroup --system django
RUN adduser --system django
RUN adduser django django
WORKDIR /opt
USER django
COPY requirements.txt ./
ENV PATH=$PATH:/home/django/.local/bin
RUN pip3 install --upgrade pip
RUN pip3 install -r requirements.txt
WORKDIR /opt/pokerproject
COPY ./pokerproject .

EXPOSE 8000
