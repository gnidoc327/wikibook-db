

---

# 위키북스 5개 DB로 서비스 만들기(책 제목 미정)

## 요구 사항(Requirements)
### 필수 사항(Required) 
> 예제 코드(프로젝트) 실행을 위한 필수 요구사항입니다.

- Python 3.11 이상, 3.13 이하
  - 설치: https://www.python.org/downloads/
    - brew 사용시: `brew install python@3.11`
- Poetry 2.1.1 이상
  - 설치: https://python-poetry.org/docs/#installing-with-the-official-installer
    - 공식 설치 방법을 권장합니다.
    - <ins>**chocolatey(window), brew(macos) 등의 패키지 매니저를 통한 설치를 권장하지 않습니다.**</ins>
      - 패키지 매니저 사용시 추후에 `poetry self update`와 같은 명령어에서 문제가 발생할 수 있습니다.
      - 의존성(ex - python)과 관련된 문제가 발생할 수 있습니다.
        - brew로 python, poetry를 설치하고 python을 업데이트하면 poetry가 동작하지 않을 수 있습니다.
        - poetry 명령어는 동작하지만 기존 가상환경이 활성화되지 않거나 의도치않게 업데이트/제거될 수 있습니다.
  - 권장 설치 플러그인: shell
    - 설치: `poetry self add poetry-plugin-shell`
    - 관련 문서: https://github.com/python-poetry/poetry-plugin-shell
- Docker Desktop 4.37 이상
  - 설치: https://www.docker.com/get-started/
  - Docker Desktop 미사용시 고려
    - Docker Engine 27.4 이상
    - Docker Compose 2.31 이상
- pre-commit 3.5 이상
  - 설치: https://pre-commit.com/#install
    - brew 사용시: `brew install pre-commit`

  
## 빠른 시작하기(Quick Install)
### 전체 실행
- FastAPI App 은 Docker Build 하고 DB와 App 모두 Docker로 실행
```shell
cp src/config/.env.sample src/config/.env 
COMPOSE_PROFILES=all docker compose up -d --build
```

### DB만 Docker 실행
- DB는 Docker로 실행
```shell
docker compose up -d
```

### 로컬에서 FastAPI App 실행
- DB를 모두 실행한 뒤에 FastAPI만 로컬에서 직접 실행
```shell
# 위에서 DB만 Docker 실행한 후에 진행
cp src/config/.env.sample src/config/.env
poetry shell
poetry install --no-root
poetry run fastapi dev src/main.py
```

## DevOps
### pre-commit
- commit 전(=pre-commit)에 linting, formatting을 적용합니다.
```shell
# git hook 적용(pre commit). .git/hooks/pre-commit 파일 생성됨
pre-commit install

# git hook과 상관없이 모든 파일에 대해서 linting, formatting
pre-commit run -a
```

### pytest
- tests 폴더 하위에 정의된 테스트 케이스를 실행합니다.
```shell
# 전체 테스트 실행. `-n auto`은 cpu 코어 수만큼 테스트를 병렬로 실행
poetry run pytest -n auto

# 특정 파일 실행
poetry run pytest tests/test_health_check.py

# 특정 클래스 실행
poetry run pytest tests/test_health_check.py::TestHealthCheck

# 특정 케이스(클래스내 함수) 실행
poetry run pytest tests/test_health_check.py::TestHealthCheck::test_health_check
```

### coverage
- 테스트 커버리지를 확인합니다.
```shell
poetry run pytest --cov=src --cov-report=term -n auto
poetry run coverage html
#poetry run pytest --cov --cov-report term --cov-report xml:coverage.xml --disable-warnings -n 5
```