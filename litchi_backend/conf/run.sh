#!/bin/bash
python manage.py collectstatic --noinput
python manage.py migrate

# run uwsgi in background
# daphne -b 0.0.0.0 -p 8090  ocean.asgi:channel_layer &
# python3.5 manage.py runworker &

use_celery="$(python -c 'from litchi_backend import *;print(settings.USE_CELERY)')"

#if [ "$use_celery" == "True" ] ; then
#  celery -A litchi_backend worker &
#  celery -A litchi_backend beat &
#fi

# start nginx
sed -i 's,NGINX_SET_REAL_IP_FROM,'"$NGINX_SET_REAL_IP_FROM"',g' /etc/nginx/nginx.conf
sed -i 's,UWSGI_SOCKET,'"$UWSGI_SOCKET"',g' /etc/nginx/conf.d/webapp.conf
sed -i 's,UWSGI_CHDIR,'"$UWSGI_CHDIR"',g' /etc/nginx/conf.d/webapp.conf
nginx
celery -A litchi_backend worker &
uwsgi /webapp/uwsgi/uwsgi.ini
