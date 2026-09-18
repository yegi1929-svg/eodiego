"""관광공사 OpenAPI 아웃바운드 호출 계수 (B_openapi.md 1, 9절) - MySQL.

공공데이터포털 일일 한도는 우리 프로세스가 재시작되든 말든 그대로 누적된다.
따라서 카운터도 프로세스 메모리가 아니라 DB에 남겨야 한도 관리가 된다.

앱 계정은 SELECT, INSERT 권한만 있어서 숫자를 +1 하지 않는다. 호출 1건마다
kto_api_call 에 1행을 추가하고, 조회할 때 COUNT 로 센다. 테이블 정의는
db/schema.sql, 오래된 기록 정리는 db/maintenance.sql (관리자).

기록하는 것은 날짜 / operation 이름뿐이다. 서비스키와 좌표는 절대 남기지
않는다 (B_openapi.md 9절).
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from shared import database

from . import config

logger = logging.getLogger("B_openapi.kto")

# 공공데이터포털 한도는 한국 날짜 기준으로 본다. 서버 시간대(EC2 기본 UTC)와
# 무관하게 KST로 계산한다 (한국은 서머타임이 없어 고정 오프셋으로 충분).
_KST = timezone(timedelta(hours=9))


def _today() -> date:
    return datetime.now(_KST).date()


def record(operation: str) -> int:
    """호출 1건을 기록하고 오늘 누적 호출 수를 돌려준다.

    재시도도 한도를 소모하므로 시도 단위로 센다. 카운터 기록이 실패해도
    관광공사 호출 자체는 막지 않는다 (경고만 남기고 -1 반환).
    """

    today = _today()
    try:
        with database.transaction() as cur:
            cur.execute(
                "INSERT INTO `kto_api_call` (`call_day`, `operation`) VALUES (%s, %s)",
                (today, operation),
            )
            cur.execute("SELECT COUNT(*) AS n FROM `kto_api_call` WHERE `call_day` = %s", (today,))
            total = cur.fetchone()["n"]
    except (database.DatabaseError, database.DatabaseConfigError) as exc:
        logger.warning("KTO 호출 기록 실패 (호출은 계속): %s", type(exc).__name__)
        return -1

    quota = config.KTO_DAILY_QUOTA
    logger.info("KTO %s (오늘 %d%s)", operation, total, f"/{quota}" if quota else "")
    if quota and total == int(quota * 0.9):
        logger.warning("관광공사 API 일일 한도의 90%%를 소모했습니다: %d/%d", total, quota)
    if quota and total == quota:
        logger.warning("관광공사 API 일일 한도에 도달했습니다: %d/%d", total, quota)
    return total


def snapshot(days: int = 7) -> dict:
    """오늘 누적치 + 최근 며칠치 이력. /internal/metrics 로 노출한다."""

    today = _today()
    with database.transaction() as cur:
        cur.execute(
            "SELECT `operation`, COUNT(*) AS n FROM `kto_api_call` WHERE `call_day` = %s GROUP BY `operation`",
            (today,),
        )
        by_operation = {r["operation"]: r["n"] for r in cur.fetchall()}
        cur.execute(
            "SELECT `call_day`, COUNT(*) AS n FROM `kto_api_call` "
            "GROUP BY `call_day` ORDER BY `call_day` DESC LIMIT %s",
            (max(days, 1),),
        )
        history = [{"date": r["call_day"].isoformat(), "total": r["n"]} for r in cur.fetchall()]

    total = sum(by_operation.values())
    quota = config.KTO_DAILY_QUOTA
    return {
        "date": today.isoformat(),
        "total": total,
        "by_operation": by_operation,
        "daily_quota": quota or None,
        "remaining": max(quota - total, 0) if quota else None,
        "history": history,
    }
