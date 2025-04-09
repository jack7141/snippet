FROM python:3.9-slim-buster

ENV PYTHONUNBUFFERED 1

RUN sed -i 's/deb.debian.org/ftp.kr.debian.org/g' /etc/apt/sources.list

RUN apt-get update \
    # dependencies for building Python packages
    && apt-get install -y build-essential \
    && apt-get install -y default-libmysqlclient-dev \
    && apt-get install -y libffi-dev \
    # cleaning up unused files
    && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
    && rm -rf /var/lib/apt/lists/*

RUN addgroup --system django \
    && adduser --system --ingroup django django

# Requirements are installed here to ensure they will be cached.
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    && rm -f requirements.txt

COPY --chown=django:django ./conf/start /start
RUN sed -i 's/\r$//g' /start
RUN chmod +x /start

COPY --chown=django:django ./conf/start-celeryworker /start-celeryworker
RUN sed -i 's/\r$//g' /start-celeryworker
RUN chmod +x /start-celeryworker

COPY --chown=django:django ./conf/start-celerybeat /start-celerybeat
RUN sed -i 's/\r$//g' /start-celerybeat
RUN chmod +x /start-celerybeat

COPY --chown=django:django ./conf/start-flower /start-flower
RUN sed -i 's/\r$//g' /start-flower
RUN chmod +x /start-flower

COPY --chown=django:django . /app

USER django

RUN mkdir -p /app/logs \
    && touch /app/logs/server.log

WORKDIR /app

CMD ["/start"]
