FROM python:3.4-alpine
COPY requirements.txt /

RUN apk update \
  && apk add --virtual build-deps gcc python3-dev musl-dev \
  && apk add postgresql-dev \
  && apk del build-deps

RUN pip install -r requirements.txt

COPY app/ /app/

WORKDIR /app

ENV APP_SETTINGS="config.DevelopmentConfig"
ENV DBPASS="hdapM1m1c4Students!"
ENV DBHOST="data.hdap.gatech.edu:5433"
ENV DBUSER="team0"
ENV DBNAME="mimic_v5"

CMD ["python", "app.py"]