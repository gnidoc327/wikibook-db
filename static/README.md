# 정적파일 관련 설명
## static 폴더
- 정적파일을 저장하는 폴더입니다.
- 정적파일이란 서버에서 변하지 않는 파일을 말합니다.
- 일반적으로 js,css,html,image 파일 등을 의미하며 이러한 파일들은 서버에서 변하지 않기 때문에 클라이언트에게 바로 전달할 수 있습니다.
- 다만 정적파일을 직접 제공할때는 보안 문제도 있지만 파일의 사이즈에 따라서 서버의 부하가 커질 수 있습니다.
  - 이러한 문제를 해결하기 위해 CDN(Content Delivery Network)를 사용할 수 있습니다.
  - 그래서 FastAPI는 기본적으로 정적파일을 제공하지 않습니다.

## Swagger UI 정적파일을 self-hosting 하는 이유
- FastAPI는 기본적으로 정적파일을 제공하지 않습니다.
- 따라서 기본 설정 사용시 Swagger UI는 정적파일을 cdn.jsdelivr.net 에 있는 컨텐츠를 사용합니다.
- 다만 인터넷이나 외부 DNS 접근이 불가능할 경우엔 문제가 될 수 있어서 self-hosting으로 설정합니다.
  - 관련 이슈: https://github.com/jsdelivr/jsdelivr/issues/18565


## Swagger UI 정적파일 다운로드 방법
- 다운로드 방법: https://fastapi.tiangolo.com/how-to/custom-docs-ui-assets/#download-the-files
```shell
cd static
wget https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js
wget https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css
wget https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js
```

- 테스트 방법: https://fastapi.tiangolo.com/how-to/custom-docs-ui-assets/#test-the-files
  - 프로젝트 실행 후 아래 주소로 접속하여 정적파일이 제대로 로딩되는지 확인합니다.
  - [http://127.0.0.1:8000/static/redoc.standalone.js](http://127.0.0.1:8000/static/redoc.standalone.js)
