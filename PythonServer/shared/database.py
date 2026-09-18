"""MySQL 접속 (A/B/C 공통).

접속 정보는 환경변수(.env)로만 받는다. 코드에 호스트/계정/비밀번호 기본값을
두지 않는다 - 빠지면 어디가 빠졌는지 알려주고 실패한다.

  DB_HOST, DB_PORT(선택, 기본 3306), DB_NAME, DB_USER, DB_PASSWORD
  DB_SSL_CA(선택): RDS 인증서 번들 경로. 지정하면 TLS로 접속한다.

앱 계정은 SELECT, INSERT 권한만 가진다. 테이블 정의는 db/schema.sql 에 있고
앱 코드에는 DDL이 없다.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from contextlib import contextmanager

import pymysql
from pymysql.cursors import DictCursor

# 호출측이 드라이버를 직접 import 하지 않도록 다시 내보낸다.
DatabaseError = pymysql.MySQLError
IntegrityError = pymysql.err.IntegrityError

_REQUIRED = ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD")
_CONNECT_TIMEOUT_SECONDS = 5

# 요청마다 새로 접속하므로 매번 호스트 이름을 조회한다. RDS 주소는 CNAME 체인이라
# 이름 조회가 간헐적으로 실패(WSATRY_AGAIN)하는 회선이 있어, 잠깐 쉬었다 다시 건다.
# 연결이 끊긴 채로 잡힌 경우(2006/2013)도 같은 방식으로 한 번 더 시도한다.
_TRANSIENT_ERROR_CODES = (2003, 2006, 2013)
_CONNECT_ATTEMPTS = 4
_RETRY_BASE_DELAY_SECONDS = 0.3


class DatabaseConfigError(RuntimeError):
    """DB 접속 환경변수가 빠졌을 때."""


def connection_settings() -> dict:
    """호출 시점의 환경변수를 읽는다 (import 시점에 고정하지 않는다)."""

    missing = [key for key in _REQUIRED if os.environ.get(key) is None]
    if missing:
        raise DatabaseConfigError(
            f"DB 접속 정보가 없습니다: {', '.join(missing)} - .env 에 설정하세요."
        )

    settings = {
        "host": os.environ["DB_HOST"],
        "port": int(os.environ.get("DB_PORT", "3306")),
        "database": os.environ["DB_NAME"],
        "user": os.environ["DB_USER"],
        "password": os.environ["DB_PASSWORD"],
    }
    ssl_ca = os.environ.get("DB_SSL_CA")
    if ssl_ca:
        settings["ssl"] = {"ca": ssl_ca}
    return settings


def connect() -> pymysql.connections.Connection:
    settings = connection_settings()
    for attempt in range(_CONNECT_ATTEMPTS):
        try:
            return pymysql.connect(
                **settings,
                charset="utf8mb4",
                cursorclass=DictCursor,
                autocommit=False,
                connect_timeout=_CONNECT_TIMEOUT_SECONDS,
            )
        except pymysql.err.OperationalError as exc:
            code = exc.args[0] if exc.args else None
            if code not in _TRANSIENT_ERROR_CODES or attempt == _CONNECT_ATTEMPTS - 1:
                raise
            time.sleep(_RETRY_BASE_DELAY_SECONDS * 2**attempt)
    raise AssertionError("unreachable")  # pragma: no cover


@contextmanager
def transaction() -> Iterator[pymysql.cursors.DictCursor]:
    """커서 하나를 트랜잭션으로 감싼다. 예외가 나면 롤백한다."""

    conn = connect()
    try:
        with conn.cursor() as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
