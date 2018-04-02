FROM python:3.4-alpine
COPY requirements.txt /

RUN apk update \
  && apk add --virtual build-deps gcc python3-dev musl-dev \
  && apk add postgresql-dev \
  && pip install psycopg2

# Install scipy dependencies
RUN echo "http://dl-8.alpinelinux.org/alpine/edge/community" >> /etc/apk/repositories
RUN apk --no-cache --update-cache add gcc gfortran python python-dev py-pip build-base wget freetype-dev libpng-dev openblas-dev
RUN ln -s /usr/include/locale.h /usr/include/xlocale.h
RUN pip install numpy scipy

RUN pip install -r requirements.txt

COPY app/ /app/

WORKDIR /app

ENV APP_SETTINGS="config.DevelopmentConfig"
ENV DBPASS="hdapM1m1c4Students!"
ENV DBHOST="data.hdap.gatech.edu:5433"
ENV DBUSER="team0"
ENV DBNAME="mimic_v5"

CMD ["python", "app.py"]