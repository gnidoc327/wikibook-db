# 위키북스 5개 DB로 서비스 만들기(책 제목 미정)

## 요구 사항(Requirements)
### 필수 사항(Required)
> 예제 코드(프로젝트) 실행을 위한 필수 요구사항입니다.

- Python 3.13 이상
  - 설치: https://www.python.org/downloads/
    - brew 사용시: `brew install python@3.13`
- uv 0.6 이상
  - 설치: https://docs.astral.sh/uv/getting-started/installation/
    - macOS / Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
    - Windows: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
    - brew 사용시: `brew install uv`
    - pip 사용시: `pip install uv`
  - 설치 확인: `uv --version`
  - uv는 Python 패키지 매니저로 pip, poetry를 대체합니다.
    - 가상환경 생성, 패키지 설치, 의존성 관리를 하나의 도구로 처리합니다.
    - Rust로 작성되어 pip 대비 10~100배 빠른 패키지 설치 속도를 제공합니다.
- Rancher Desktop 1.22 이상
  - 설치: https://rancherdesktop.io/
    - brew 사용시: `brew install --cask rancher`
  - Container Engine은 `dockerd(moby)`를 선택하면 기존 docker 명령어를 그대로 사용할 수 있습니다.
  - 권장 리소스 설정: **CPU 4 core / Memory 6 GB**
    - 최소: CPU 2 core / Memory 4 GB
    - 6개 컨테이너(MySQL, Valkey, MongoDB, OpenSearch, OpenSearch Dashboards, RabbitMQ)를 동시에 실행합니다.
- pre-commit 3.5 이상
  - 설치: https://pre-commit.com/#install
    - brew 사용시: `brew install pre-commit`

## 프로젝트 구조(Project Structure)

챕터별로 점진적으로 DB를 추가하는 구조입니다. 루트 `pyproject.toml`을 공유하며 챕터별로 독립적인 FastAPI 서버를 실행합니다.

| Chapter | DB |
|---------|------|
| ch01 | MySQL + S3 (MinIO) |
| ch02 | ch01 + OpenSearch |
| ch03 | ch02 + Valkey |
| ch04 | ch03 + MongoDB |
| ch05 | ch04 + RabbitMQ |

```
wikibook-25-db/
├── pyproject.toml          # 공유 의존성 및 도구 설정
├── docker-compose.yml      # DB 인프라
├── .pre-commit-config.yaml # ruff lint + format
├── ch01/
│   ├── __init__.py
│   ├── main.py             # FastAPI app
│   ├── config/
│   │   ├── .env.sample     # 환경변수 샘플
│   │   └── config.py       # pydantic-settings
│   ├── dependencies/
│   │   └── mysql.py
│   ├── models/
│   │   ├── mixin.py
│   │   └── user.py
│   └── tests/              # __init__.py 없음
│       ├── conftest.py
│       └── test_health_check.py
├── ch02/ ~ ch05/           # 동일 구조, DB 점진 추가
└── ...
```

## 빠른 시작하기(Quick Start)

### 1. DB 실행
```shell
docker compose up -d
```

### 2. 환경변수 설정
```shell
# 사용할 챕터의 .env.sample을 .env로 복사
cp ch01/config/.env.sample ch01/config/.env
```

### 3. 의존성 설치
```shell
uv sync
```

### 4. FastAPI 서버 실행
```shell
# 챕터별로 구분하여 실행
uv run fastapi dev ch01/main.py
uv run fastapi dev ch02/main.py
uv run fastapi dev ch03/main.py
uv run fastapi dev ch04/main.py
uv run fastapi dev ch05/main.py
```

### 5. Consumer 실행 (ch05 전용)
FastAPI 서버가 먼저 실행된 상태에서 별도 터미널에 실행합니다.
```shell
uv run python -m ch05.consumer
```

메시지 흐름:
```
RabbitMQ → consumer (aio-pika) → POST /internal/messages → FastAPI
```

## uv 사용법(uv Usage)
```shell
# 의존성 설치 (pyproject.toml 기반, 가상환경 자동 생성)
uv sync

# 패키지 추가
uv add <package-name>

# 개발 의존성 추가
uv add --group dev <package-name>

# 패키지 제거
uv remove <package-name>

# 가상환경 내에서 명령어 실행
uv run <command>
```

## DevOps

### Lint & Format
```shell
# ruff로 lint (git 추적 여부와 관계없이 모든 파일에 적용)
uv run ruff check --fix .

# ruff로 formatting
uv run ruff format .
```

### pre-commit
- commit 전(=pre-commit)에 ruff lint + format을 자동으로 적용합니다.
- `pre-commit run -a`는 git에 추적(tracked)된 파일에만 실행됩니다.
```shell
# git hook 적용. .git/hooks/pre-commit 파일 생성됨
pre-commit install

# 추적된 파일 전체에 대해 linting, formatting 실행
pre-commit run -a
```

### pytest
- 각 챕터 폴더(`chXX/tests/`) 안에 테스트 코드가 위치합니다.
- 테스트 디렉토리에는 `__init__.py`를 사용하지 않으며, `--import-mode=importlib`로 동일 파일명 충돌을 해결합니다.
- `pyproject.toml` addopts에 `-n auto --dist=loadfile`이 설정되어 **챕터 내 병렬 실행이 기본**입니다.
- **챕터별로 따로 실행**해야 합니다. 여러 챕터를 동시에 실행하면 MySQL DDL 충돌이 발생합니다.

```shell
# 챕터별 테스트 실행 (권장)
uv run pytest ch01/tests/ -v
uv run pytest ch02/tests/ -v
uv run pytest ch03/tests/ -v
uv run pytest ch04/tests/ -v
uv run pytest ch05/tests/ -v

# 특정 파일 실행
uv run pytest ch01/tests/test_health_check.py

# 특정 클래스 실행
uv run pytest ch01/tests/test_health_check.py::TestHealthCheck

# 특정 케이스 실행
uv run pytest ch01/tests/test_health_check.py::TestHealthCheck::test_health_check
```

### coverage
```shell
uv run pytest --cov=ch01 --cov-report=term ch01/tests/
uv run coverage html
```
