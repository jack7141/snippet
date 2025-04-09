#!/bin/bash
python manage.py collectstatic --noinput
python manage.py migrate

sed -i 's,NGINX_SET_REAL_IP_FROM,'"$NGINX_SET_REAL_IP_FROM"',g' /etc/nginx/nginx.conf
sed -i 's,UWSGI_SOCKET,'"$UWSGI_SOCKET"',g' /etc/nginx/conf.d/webapp.conf
sed -i 's,UWSGI_CHDIR,'"$UWSGI_CHDIR"',g' /etc/nginx/conf.d/webapp.conf

# start nginx
nginx
uwsgi /webapp/uwsgi/uwsgi.ini
