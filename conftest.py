import re
import sys

import pytest


@pytest.hookimpl(tryfirst=True)
def pytest_cmdline_main(config: pytest.Config) -> int | None:
    """여러 챕터를 동시에 테스트하는 것을 방지합니다.

    [에러 원인]
    모든 챕터는 동일한 MySQL 데이터베이스를 공유합니다.
    각 챕터의 init_db fixture(scope="session")는 테스트 시작 시
    Base.metadata.drop_all() → create_all()을 실행해 스키마를 재구성합니다.

    여러 챕터가 동시에 실행되면:
    - ch04의 init_db가 테이블을 DROP+CREATE 하는 순간
    - ch05의 init_db가 이미 생성해둔 ch05 스키마가 사라집니다.
    - 그 반대도 마찬가지입니다.
    → 스키마 충돌로 SQLAlchemy 쿼리가 실패하고, 테스트가 무작위로 깨집니다.

    [해결] README.md의 '### pytest' 섹션을 참고하세요.
    챕터를 하나씩 지정해 실행하세요:
      uv run pytest ch01/tests/ -v
      uv run pytest ch05/tests/ -v
    """
    # xdist 워커 프로세스 또는 이미 처리한 경우 스킵
    if hasattr(config, "workerinput") or getattr(config, "_chapter_check_done", False):
        return None

    config._chapter_check_done = True  # type: ignore[attr-defined]

    args = config.args or []
    chapters: set[str] = set()
    for arg in args:
        m = re.match(r"(ch\d+)[/\\]?", str(arg))
        if m:
            chapters.add(m.group(1))

    if len(chapters) > 1:
        chapter_list = ", ".join(sorted(chapters))
        msg = (
            f"\n[오류] 여러 챕터를 동시에 테스트할 수 없습니다.\n"
            f"  감지된 챕터: {chapter_list}\n\n"
            f"[원인]\n"
            f"  모든 챕터가 동일한 MySQL DB를 공유합니다.\n"
            f"  init_db fixture가 실행될 때 스키마를 DROP + CREATE하므로\n"
            f"  여러 챕터가 동시에 실행되면 스키마가 서로를 덮어씁니다.\n\n"
            f"[해결] 챕터를 하나씩 실행하세요:\n"
            f"  uv run pytest ch01/tests/ -v\n"
            f"  uv run pytest ch05/tests/ -v\n\n"
            f"  자세한 내용은 README.md '### pytest' 섹션을 참조하세요."
        )
        print(f"ERROR:{msg}", file=sys.stderr)
        return pytest.ExitCode.USAGE_ERROR

    return None
