# Order Management System
## Local Development
* 프로젝트 루트 디렉토리에 `.env` 파일 생성
* 도커 컨테이너 빌드
```shell
docker-compose -f docker-compose-local.yml build
```
* 도커 컨테이너 시작
```shell
docker-compose -f docker-compose-local.yml up
```
* Django admin 접근
    * URL: `http://127.0.0.1/admin/`
    * ID: admin@fount.co
    * PW: admin
