"""전체 테스트 공통 설정 - MySQL 테스트 DB.

- 접속 정보는 앱과 똑같이 .env 의 DB_* 를 쓴다 (앱 계정 eodiegoServer, SELECT/INSERT 전용).
  그래서 테스트가 통과하면 "그 권한만으로 기능이 동작한다"는 것도 함께 검증된다.
- DB 이름만 항상 테스트용(TEST_DB_NAME, 기본 eodiego_test)으로 바꾼다.
  운영 DB(eodiego)에는 절대 쓰지 않는다.
- 앱 계정은 DELETE 권한이 없어 테스트가 끝나도 데이터를 지우지 못한다. 대신
  아이디/날짜를 테스트마다 고유하게 만들어 서로 섞이지 않게 한다.
- 테스트 DB가 없으면(db/setup_local.sql 미실행) DB가 필요한 테스트는 이유와 함께 건너뛴다.
"""

import os
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent


def _load_db_env() -> None:
    env_file = _ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("DB_") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())
    os.environ["DB_NAME"] = os.environ.get("TEST_DB_NAME", "eodiego_test")


_load_db_env()


@pytest.fixture(scope="session")
def mysql_db():
    """테스트 DB 접속 + 테이블 존재 확인. 안 되면 건너뛴다."""

    from shared import database

    try:
        with database.transaction() as cur:
            cur.execute("SELECT 1 FROM `user` LIMIT 1")
            cur.execute("SELECT 1 FROM `kto_api_call` LIMIT 1")
            cur.execute("SELECT 1 FROM `llm_request` LIMIT 1")
    except Exception as exc:  # noqa: BLE001 - 어떤 이유든 DB가 준비 안 된 것
        pytest.skip(f"MySQL 테스트 DB({os.environ['DB_NAME']}) 사용 불가: {type(exc).__name__}: {exc}")
    return os.environ["DB_NAME"]
