"""LLM 하루 요청 수 제한 + 토큰 사용량 기록 - MySQL.

OpenAI 계정 한도가 하루 50회(RPD)라서, 한도를 넘겨 429를 받기 전에 우리가
먼저 멈추고 기본 문구로 전환한다. 서버를 재시작해도 오늘 쓴 횟수가 남도록
DB에 둔다.

앱 계정은 SELECT, INSERT 권한만 있어서 숫자를 +1 하지 않는다. 요청 1건마다
llm_request 에 1행, 응답 토큰은 llm_token_usage 에 1행을 추가하고 COUNT/SUM
으로 센다. 테이블 정의는 db/schema.sql.

날짜는 UTC 기준으로 센다. 제공사의 하루 리셋 시점이 확실하지 않아서, 상한을
실제 한도보다 낮게(45/50) 잡아 여유를 둔다.
"""

from __future__ import annotations

import logging
import threading
from datetime import date, datetime, timezone

from shared import database

from . import config

logger = logging.getLogger(__name__)

# 같은 프로세스 안에서 동시에 예약할 때의 경합을 줄인다. (서버 여러 대의 경합은
# INSERT ... SELECT 한 문장으로 좁히고, 남는 틈은 상한 45/50의 여유분으로 흡수한다.)
_lock = threading.Lock()


def _today() -> date:
    return datetime.now(timezone.utc).date()


def try_reserve() -> bool:
    """요청 1회분을 예약한다. 오늘 상한에 도달했으면 False (호출하지 말 것).

    실패한 요청도 제공사 한도를 깎으므로, 호출 "직전"에 센다.
    DB에 기록할 수 없으면 한도를 확인할 수 없으므로 부르지 않는다 (False).
    """

    limit = config.LLM_DAILY_REQUEST_LIMIT
    today = _today()
    try:
        with _lock, database.transaction() as cur:
            if not limit:
                cur.execute(
                    "INSERT INTO `llm_request` (`request_day`, `model`) VALUES (%s, %s)",
                    (today, config.LLM_MODEL),
                )
                return True
            # 오늘 건수가 상한 미만일 때만 1행을 추가한다 (한 문장으로 확인+추가).
            cur.execute(
                "INSERT INTO `llm_request` (`request_day`, `model`) "
                "SELECT %s, %s FROM DUAL "
                "WHERE (SELECT COUNT(*) FROM `llm_request` WHERE `request_day` = %s) < %s",
                (today, config.LLM_MODEL, today, limit),
            )
            return cur.rowcount > 0
    except (database.DatabaseError, database.DatabaseConfigError) as exc:
        logger.warning("LLM 요청 한도 확인 불가 -> 호출하지 않음: %s", type(exc).__name__)
        return False


def record_tokens(input_tokens: int, output_tokens: int) -> None:
    try:
        with database.transaction() as cur:
            cur.execute(
                "INSERT INTO `llm_token_usage` (`usage_day`, `model`, `input_tokens`, `output_tokens`) "
                "VALUES (%s, %s, %s, %s)",
                (_today(), config.LLM_MODEL, input_tokens, output_tokens),
            )
    except (database.DatabaseError, database.DatabaseConfigError) as exc:
        logger.warning("LLM 토큰 사용량 기록 실패: %s", type(exc).__name__)


def snapshot() -> dict:
    today = _today()
    with database.transaction() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM `llm_request` WHERE `request_day` = %s", (today,))
        used = cur.fetchone()["n"]
        cur.execute(
            "SELECT COALESCE(SUM(`input_tokens`), 0) AS i, COALESCE(SUM(`output_tokens`), 0) AS o "
            "FROM `llm_token_usage` WHERE `usage_day` = %s",
            (today,),
        )
        tokens = cur.fetchone()

    limit = config.LLM_DAILY_REQUEST_LIMIT
    return {
        "date_utc": today.isoformat(),
        "model": config.LLM_MODEL,
        "requests": used,
        "daily_limit": limit or None,
        "remaining": max(limit - used, 0) if limit else None,
        "input_tokens": int(tokens["i"]),
        "output_tokens": int(tokens["o"]),
    }
