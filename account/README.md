# Litchi Account API Server
일임계약 가원장 관리 서버

## Tech
* [Django] - Python 웹 애플리케이션 프레임워크
* [Django Rest Framework] - RESTFul Web API
* [Django Rest Swagger] - [Django Rest Framework]을 위한 문서 생성기

## System Requirements
[python] 3.7이상 
 
## Installation
Litchi Account API Server를 실행하려면 [python] 3.7 이상이 필요합니다.

종속 패키지를 설치합니다.

```sh
$ pip3 install virtualenv
$ virtualenv -p python3 venv
$ source venv/bin/activate
$ pip3 install -r requirements.txt
```

기본 설정 파일을 사용한 서버 시작 방법은 아래와 같습니다.

```sh
$ python manage.py migrate
$ python manage.py runserver
```

특정 설정 파일을 사용한 서버 시작 방법은 아래와 같습니다.
환경변수 `RUNNING_ENV의` 값을 참조하여 적용되며 `local`, `development`, `stage`, `production` 4가지가 있습니다.

> 각 설정 파일의 정의는 `settings`폴더에 들어있으며, 비밀번호와 같은 노출되면 위험한 설정값의 경우 `settings`폴더의 `secrets.json` 파일에 정의 합니다.

```sh
$ export RUNNING_ENV=production
$ python manage.py runserver
```

서버 실행 후, 사용하는 브라우저에 서버 주소를 입력하여 동작을 확인합니다.

```sh
http://127.0.0.1:8000
```

## Docker
Litchi Account API Server는 Docker 컨테이너로 설치하고 배포가 가능합니다.

기본적으로 이 프로젝트에 적용된 Docker는 포트 80, 443을 노출하고 있습니다.
빌드 준비가 되면 Dockerfile을 사용하여 이미지를 빌드합니다.

```sh
$ docker build -t litchi_account .
```

빌드가 정상적으로 끝났을때, 빌드된 Docker 이미지를 기반으로 컨테이너를 생성합니다.
컨테이너 생성시 컨테이너에 접속할 포트를 호스트 포트와 매핑합니다. 이 예제에서는 호스트포트 8000을 컨테이너 포트 80(또는 Dockerfile에 노출된 포트)로 매핑합니다.

```sh
$ docker run -d -p 8000:80 litchi_account
```

컨테이너가 정상적으로 생성된 경우, 사용하는 브라우저에 서버 주소를 입력하여 동작을 확인합니다.

```sh
127.0.0.1:8000
```

## API Document

API에 대한 문서는 swagger를 통해 자동생성되도록 되어있습니다.
각 API는 `버전`이 존재하며 버전의 룰은 `"v{version}"`으로 적용됩니다.
> 예) v1, v2, v3 ...

Swagger API 문서 주소는 `/api/v{version}/swagger`입니다.
> 예) /api/v1/swagger

Redoc API 문서 주소는 `/api/v{version}/redoc`입니다.
> 예) /api/v1/redoc

## Settings
### Environments


[//]: # (These are reference links used in the body of this note and get stripped out when the markdown processor does its job. There is no need to format nicely because it shouldn't be seen. Thanks SO - http://stackoverflow.com/questions/4823468/store-comments-in-markdown-syntax)

   [fount logo]: <https://fount.co/wp-content/uploads/2017/07/fount-ci@2x.png>
   [python]: <https://www.python.org/>
   [Django]: <https://www.djangoproject.com/>
   [Django Rest Framework]: <http://www.django-rest-framework.org/>
   [Django Rest Swagger]: <https://django-rest-swagger.readthedocs.io>
