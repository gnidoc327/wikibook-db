FROM python:3.11

RUN pip install -U poetry
WORKDIR /app

# 의존성 레이어를 캐시하기 위해 poetry.lock과 pyproject.toml만 먼저 복사합니다.
COPY poetry.lock pyproject.toml /app/

RUN poetry install --no-root

# 변경이 잦은 파일(코드)을 복사합니다.
COPY static /app/static
COPY src /app/src
