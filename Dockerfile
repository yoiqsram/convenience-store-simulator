# STAGE 1: Build dependencies
FROM python:3.8-alpine as build
RUN apk add --no-cache git
RUN apk add --no-cache postgresql-dev build-base

WORKDIR /app
ENV PYTHONPATH=/app
COPY requirements.txt .

RUN pip install -U pip
RUN pip install -r requirements.txt
RUN pip install psycopg2

# STAGE 2: Runtime image
FROM build as runtime

# Use different value for --build-arg CACHEBUST to recache current stage
ARG CACHEBUST=0
COPY . .

# Verify required python packages
RUN pip install -r requirements.txt

ENTRYPOINT [ "python", "-m", "simulator" ]
CMD []
