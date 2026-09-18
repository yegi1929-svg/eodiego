"""화면(이미 만들어진 HTML/JS)이 그대로 쓸 수 있도록 API 응답을 표시용으로
가공하는 순수 로직. 렌더링(HTML/CSS)은 만들지 않는다 - 여기서는 dict/문구만
만들고, 기존 화면의 JS가 이 값을 자기 DOM에 꽂아 넣는다.

D_frontend.md 6, 7, 9, 10절 규칙을 그대로 코드로 옮긴 것이다.
"""

from __future__ import annotations

from . import config
from .api_client.errors import UpstreamRejectedError, UpstreamUnavailableError

# ---------------------------------------------------------------------------
# 6절: 집중률 UI - "실시간 혼잡도"처럼 표현하지 않는다.
# ---------------------------------------------------------------------------


def congestion_label(rate: float | None, has_data: bool) -> str:
    if not has_data or rate is None:
        return "혼잡도 예측 정보 없음"
    if rate >= config.CONGESTION_DISPLAY_THRESHOLD:
        return "예측 집중률 높음"
    if rate >= config.CONGESTION_DISPLAY_THRESHOLD * 0.5:
        return "예측 집중률 보통"
    return "예측 집중률 낮음"


def is_high_congestion(rate: float | None, has_data: bool) -> bool:
    return has_data and rate is not None and rate >= config.CONGESTION_DISPLAY_THRESHOLD


# ---------------------------------------------------------------------------
# 5절: 일정 화면 - order/visit_time/note/summary를 활용해 카드 형태로 가공.
# ---------------------------------------------------------------------------


def plan_display_context(plan: dict) -> dict:
    """Plan(dict) -> 화면이 바로 반복 렌더링할 수 있는 형태.

    반환 예:
    {
      "title": "제주 1일 코스",
      "summary": "...",
      "travel_date": "20260828",
      "items": [
        {"order": 1, "visit_time": "10:00", "name": "보덕사", "note": "..."},
        ...
      ],
    }
    """

    items = sorted(plan.get("items", []), key=lambda i: i["order"])
    result_items = []
    for i in items:
        note = i.get("note") or "혼잡도 예측 정보 없음"
        # C가 congestion_label/high_congestion을 따로 내려준다. note는 LLM
        # 설명으로 덮이므로 note 문자열 비교는 폴백으로만 쓴다.
        label = i.get("congestion_label") or (note if note.startswith("예측 집중률") else None)
        high = bool(i.get("high_congestion")) or note == "예측 집중률 높음"
        entry = {
            "content_id": i["content_id"],
            "order": i["order"],
            "visit_time": i["visit_time"],
            "name": i["name"],
            "note": note,
            "congestion_label": label or "혼잡도 예측 정보 없음",
            "high_congestion": high,
            # 최종 일정에 뽑힌 장소의 상세정보 (소개문/운영시간/휴무일). 없으면 None.
            "detail": i.get("detail"),
        }
        if high:
            entry["replan_prompt"] = replan_prompt(i["name"])
        result_items.append(entry)

    return {
        "title": plan.get("title", ""),
        "summary": plan.get("summary", ""),
        "travel_date": plan.get("travel_date", ""),
        "items": result_items,
    }


# ---------------------------------------------------------------------------
# 7절: 재추천 UX - 특정 항목만 바뀌었음을 명확히 알려준다.
# ---------------------------------------------------------------------------


def replan_prompt(item_name: str) -> dict:
    return {
        "message": "예측 집중률이 높습니다.\n다른 관광지를 추천받으시겠습니까?",
        "target_name": item_name,
    }


def replan_result_context(replan_response: dict) -> dict:
    return {
        "plan": plan_display_context(replan_response["plan"]),
        "changed_content_id": replan_response["replaced_content_id"],
        "change_reason": replan_response["replacement_reason"],
    }


# ---------------------------------------------------------------------------
# 9절: API 오류 UI - "알 수 없는 오류"로 뭉뚱그리지 않는다.
# ---------------------------------------------------------------------------


# 상류(A/B/C)가 준 에러 코드별 문구. 상황을 아는 코드가 오면 화면 맥락보다
# 이쪽을 우선한다 - 회원가입 실패에 "비밀번호를 확인해주세요"가 뜨던 문제.
_CODE_MESSAGES: dict[str, str] = {
    "SESSION_EXPIRED": "세션이 만료되었습니다.\n다시 로그인해주세요.",
    "AUTH_REQUIRED": "로그인이 필요합니다.",
    "INVALID_CREDENTIALS": "아이디 또는 비밀번호가 올바르지 않습니다.",
    "DUPLICATE_USER": "이미 사용 중인 아이디입니다.",
    "VALIDATION_ERROR": "입력값을 다시 확인해주세요.",
    "NOT_FOUND": "요청하신 항목을 찾을 수 없습니다.",
}

_FRIENDLY_MESSAGES: dict[str, str] = {
    "regions": "여행 지역 목록을 불러오지 못했습니다.\n잠시 후 다시 시도해주세요.",
    "register": "회원가입에 실패했습니다.\n입력값을 확인해주세요.",
    "places_nearby": "관광지 정보를 불러오지 못했습니다.\n잠시 후 다시 시도해주세요.",
    "congestion": "집중률 정보를 가져오지 못했습니다.\n관광지 정보만으로 추천을 계속합니다.",
    "plan_generate": "일정 생성에 실패했습니다.\n다시 시도해주세요.",
    "plan_replan": "재추천에 실패했습니다.\n잠시 후 다시 시도해주세요.",
    "auth": "로그인에 실패했습니다.\n아이디와 비밀번호를 확인해주세요.",
    "session_expired": "세션이 만료되었습니다.\n다시 로그인해주세요.",
    "plan_save": "일정 저장에 실패했습니다.\n다시 시도해주세요.",
    "generic": "요청을 처리하지 못했습니다.\n잠시 후 다시 시도해주세요.",
}


def error_context(context_key: str, exc: Exception) -> dict:
    """API 호출 실패를 화면에 보여줄 {message, retryable} 형태로 변환한다.

    - has_data=False(정상, 데이터 없음)는 이 함수를 타지 않는다. 이 함수는
      진짜 API 실패(UpstreamUnavailableError/UpstreamRejectedError)만 다룬다.
    """

    code = exc.code if isinstance(exc, UpstreamRejectedError) else None
    message = _CODE_MESSAGES.get(code) if code else None
    if message is None:
        message = _FRIENDLY_MESSAGES.get(context_key, _FRIENDLY_MESSAGES["generic"])

    retryable = isinstance(exc, UpstreamUnavailableError) or (
        isinstance(exc, UpstreamRejectedError) and exc.status_code >= 500
    )

    # code를 그대로 실어 보낸다. 이게 없으면 화면이 "로그인이 필요함"과
    # "서버 오류"를 구분하지 못해 로그인 창을 띄울 수 없다.
    return {"message": message, "retryable": retryable, "code": code}


# ---------------------------------------------------------------------------
# 10절: 로딩/빈 상태 - 화면이 status 필드 하나로 분기할 수 있게 감싼다.
# ---------------------------------------------------------------------------


def status_envelope(status: str, data=None, empty_message: str | None = None) -> dict:
    """status: "success" | "empty" | "error". "loading"은 화면(JS)이 요청
    시작 시 자체적으로 표시하므로 서버가 내려줄 필요는 없다."""

    envelope = {"status": status}
    if status in ("success", "error"):
        envelope["data"] = data
    elif status == "empty":
        envelope["message"] = empty_message or "표시할 항목이 없습니다."
    return envelope
