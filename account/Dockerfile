FROM python:3.7
MAINTAINER Kyoungsu Kim <kks@fount.co>

ARG GIT_USERNAME=gitlab
ARG GIT_PASSWORD=password

ADD ./requirements.txt /webapp/server/requirements.txt
ADD ./conf /webapp/server/conf

RUN apt-get update \
    && apt-get install -y nginx \
    && mkdir -p /webapp/uwsgi \
    && mkdir -p /webapp/server \
    && pip install --no-cache-dir uwsgi pip --upgrade \
    && python /webapp/server/conf/replace_requirements.py /webapp/server/requirements.txt ${GIT_USERNAME} ${GIT_PASSWORD} \
    && pip install --no-cache-dir -r /webapp/server/requirements.txt \
    && rm -rf /webapp/server/requirements.txt

ADD . /webapp/server
WORKDIR /webapp/server

ENV NGINX_SET_REAL_IP_FROM="172.18.0.0/16"\
    UWSGI_SOCKET="/webapp/uwsgi/webapp.sock"\
    UWSGI_PID="/webapp/uwsgi/webapp.pid"\
    UWSGI_CHDIR="/webapp/server"\
    UWSGI_MODULE="account.wsgi"\
    RUNNING_ENV="base"

RUN mv ./conf/run.sh / \
    && chmod 755 /run.sh \
    && mv ./conf/nginx.conf /etc/nginx/nginx.conf \
    && mv ./conf/webapp.conf /etc/nginx/conf.d/webapp.conf \
    && mv ./conf/uwsgi.ini /webapp/uwsgi/uwsgi.ini

CMD ["/run.sh"]

