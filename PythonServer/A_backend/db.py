"""DB 접근 계층 (A_backend_auth.md 3절) - MySQL.

DB에는 회원/인증 정보와 우리가 만든 일정 정보만 저장한다. 관광공사 원본
데이터는 저장하지 않고, plan_item에는 content_id를 참조값으로만 저장한다.
좌표는 절대 저장하지 않는다.

- 테이블 정의는 db/schema.sql 에만 있다. 이 파일에는 DDL이 없다.
- 앱 계정은 SELECT, INSERT 권한만 있다. 그래서 지우거나 고치지 않고 기록을 추가한다:
    로그아웃  -> session_revocation 에 폐기 기록 추가
    일정 삭제 -> plan_deletion 에 삭제 기록 추가
- 모든 쿼리는 파라미터 바인딩으로 SQL Injection을 막는다.
"""

from __future__ import annotations

from datetime import datetime, timezone

from shared import database
from shared.schemas import PlanItem, SavedPlan


class DuplicateUserError(Exception):
    pass


def ping() -> None:
    """서버 기동 시 DB 접속과 테이블 존재를 확인한다 (없으면 바로 실패)."""

    with database.transaction() as cur:
        cur.execute("SELECT 1 FROM `user` LIMIT 1")


def _utc(epoch_seconds: float) -> datetime:
    """DB의 DATETIME은 시간대가 없으므로 항상 UTC로 넣고 UTC로 비교한다."""

    return datetime.fromtimestamp(epoch_seconds, timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# 회원
# ---------------------------------------------------------------------------


def create_user(username: str, password_hash: str) -> int:
    try:
        with database.transaction() as cur:
            cur.execute(
                "INSERT INTO `user` (`username`, `password_hash`) VALUES (%s, %s)",
                (username, password_hash),
            )
            return cur.lastrowid
    except database.IntegrityError as exc:
        raise DuplicateUserError(f"username={username} 이미 존재") from exc


def get_user_by_username(username: str) -> dict | None:
    with database.transaction() as cur:
        cur.execute(
            "SELECT `user_id`, `username`, `password_hash` FROM `user` WHERE `username` = %s",
            (username,),
        )
        return cur.fetchone()


def get_user_by_id(user_id: int) -> dict | None:
    with database.transaction() as cur:
        cur.execute(
            "SELECT `user_id`, `username`, `password_hash` FROM `user` WHERE `user_id` = %s",
            (user_id,),
        )
        return cur.fetchone()


# ---------------------------------------------------------------------------
# 저장 일정
# ---------------------------------------------------------------------------


def create_plan(user_id: int, title: str, travel_date: str, items: list[PlanItem]) -> int:
    with database.transaction() as cur:
        cur.execute(
            "INSERT INTO `plan` (`user_id`, `title`, `travel_date`) VALUES (%s, %s, %s)",
            (user_id, title, travel_date),
        )
        plan_id = cur.lastrowid
        if items:
            cur.executemany(
                "INSERT INTO `plan_item` (`plan_id`, `content_id`, `name`, `item_order`, `visit_time`, `note`) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                [(plan_id, i.content_id, i.name, i.order, i.visit_time, i.note) for i in items],
            )
    return plan_id


# 삭제 기록이 있는 일정은 조회에서 뺀다.
_NOT_DELETED = "NOT EXISTS (SELECT 1 FROM `plan_deletion` d WHERE d.`plan_id` = p.`plan_id`)"


def _items_by_plan(cur, plan_ids: list[int]) -> dict[int, list[PlanItem]]:
    if not plan_ids:
        return {}
    placeholders = ", ".join(["%s"] * len(plan_ids))
    cur.execute(
        "SELECT `plan_id`, `content_id`, `name`, `item_order`, `visit_time`, `note` "
        f"FROM `plan_item` WHERE `plan_id` IN ({placeholders}) ORDER BY `plan_id`, `item_order`",
        plan_ids,
    )
    grouped: dict[int, list[PlanItem]] = {pid: [] for pid in plan_ids}
    for r in cur.fetchall():
        grouped[r["plan_id"]].append(
            PlanItem(
                content_id=r["content_id"], name=r["name"], order=r["item_order"],
                visit_time=r["visit_time"], note=r["note"],
            )
        )
    return grouped


def list_plans(user_id: int) -> list[SavedPlan]:
    with database.transaction() as cur:
        cur.execute(
            "SELECT p.`plan_id`, p.`title`, p.`travel_date` FROM `plan` p "
            f"WHERE p.`user_id` = %s AND {_NOT_DELETED} "
            "ORDER BY p.`created_at` DESC, p.`plan_id` DESC",
            (user_id,),
        )
        plans = cur.fetchall()
        items = _items_by_plan(cur, [p["plan_id"] for p in plans])
    return [
        SavedPlan(plan_id=p["plan_id"], title=p["title"], travel_date=p["travel_date"], items=items[p["plan_id"]])
        for p in plans
    ]


def get_plan(user_id: int, plan_id: int) -> SavedPlan | None:
    with database.transaction() as cur:
        cur.execute(
            "SELECT p.`plan_id`, p.`title`, p.`travel_date` FROM `plan` p "
            f"WHERE p.`plan_id` = %s AND p.`user_id` = %s AND {_NOT_DELETED}",
            (plan_id, user_id),
        )
        plan = cur.fetchone()
        if plan is None:
            return None
        items = _items_by_plan(cur, [plan_id])
    return SavedPlan(plan_id=plan["plan_id"], title=plan["title"], travel_date=plan["travel_date"], items=items[plan_id])


def delete_plan(user_id: int, plan_id: int) -> bool:
    """삭제 기록을 추가한다. 본인 일정이고 아직 삭제되지 않았을 때만 기록된다."""

    with database.transaction() as cur:
        cur.execute(
            "INSERT IGNORE INTO `plan_deletion` (`plan_id`, `user_id`) "
            "SELECT p.`plan_id`, p.`user_id` FROM `plan` p "
            f"WHERE p.`plan_id` = %s AND p.`user_id` = %s AND {_NOT_DELETED}",
            (plan_id, user_id),
        )
        return cur.rowcount > 0


# ---------------------------------------------------------------------------
# 세션 (A_backend_auth.md 4절) - auth.py가 이 함수들만 사용한다.
# ---------------------------------------------------------------------------


def create_session(token_hash: str, user_id: int, expires_at: float) -> None:
    with database.transaction() as cur:
        cur.execute(
            "INSERT INTO `session` (`token_hash`, `user_id`, `expires_at`) VALUES (%s, %s, %s)",
            (token_hash, user_id, _utc(expires_at)),
        )


def get_session_user(token_hash: str, now: float) -> int | None:
    """만료되지 않았고 폐기(로그아웃) 기록도 없는 세션이면 user_id, 아니면 None."""

    with database.transaction() as cur:
        cur.execute(
            "SELECT s.`user_id` FROM `session` s "
            "LEFT JOIN `session_revocation` r ON r.`token_hash` = s.`token_hash` "
            "WHERE s.`token_hash` = %s AND s.`expires_at` > %s AND r.`token_hash` IS NULL",
            (token_hash, _utc(now)),
        )
        row = cur.fetchone()
    return row["user_id"] if row else None


def revoke_session(token_hash: str) -> None:
    """로그아웃: 세션을 지우지 않고 폐기 기록을 추가한다.

    존재하는 세션일 때만 기록한다 - 아무 쿠키 값으로 로그아웃을 불러 기록을
    쌓는 것을 막는다.
    """

    with database.transaction() as cur:
        cur.execute(
            "INSERT IGNORE INTO `session_revocation` (`token_hash`) "
            "SELECT `token_hash` FROM `session` WHERE `token_hash` = %s",
            (token_hash,),
        )
