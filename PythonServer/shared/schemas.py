"""팀 공통 API 계약 (schemas.py).

A/B/C/D 모든 서비스가 공유하는 Pydantic 모델이다.
임의로 변경하지 않는다. 변경이 필요하면 팀에 먼저 공유한다.

A_backend_auth.md 2절의 계약을 기준으로 하고, B_openapi.md 7절에서 제안한
Place 보완 필드(content_type_id/category/운영시간/휴무일/예상 체류시간)만
선택적(Optional)으로 추가했다. 관광공사 원본 필드를 무분별하게 복사하지
않기 위해 실제로 C(일정 생성)/D(화면)가 쓰는 필드만 남겼다.
"""

from __future__ import annotations

from pydantic import BaseModel


class Place(BaseModel):
    content_id: str
    name: str
    addr: str
    map_x: float
    map_y: float
    dist: float
    image: str | None = None

    # --- B_openapi.md 7절: 필요한 데이터만 선택적으로 추가 ---
    content_type_id: str | None = None
    category: str | None = None
    use_time: str | None = None  # 운영시간
    rest_date: str | None = None  # 휴무일
    expected_stay_minutes: int | None = None  # 예상 체류시간(분)
    overview: str | None = None  # 관광공사 소개문 (detailCommon2). LLM 근거 자료로도 쓴다.


class PlaceDetailsRequest(BaseModel):
    """최종 일정에 뽑힌 장소들의 상세정보 일괄 조회."""

    content_ids: list[str]


class Region(BaseModel):
    """화면의 "어디를 둘러볼까요?" 지역 선택지.

    화면이 좌표를 하드코딩하지 않도록 B가 대표 좌표까지 함께 내려준다
    (D_frontend.md 11절: 화면은 관광 데이터를 직접 알고 있지 않는다).
    """

    code: str
    name: str
    map_x: float
    map_y: float


class DayRate(BaseModel):
    date: str  # "YYYYMMDD"
    rate: float  # 예측 집중률(%). "현재 혼잡도"가 아니다.


class CongestionTarget(BaseModel):
    """집중률 조회 대상.

    집중률 API는 관광지 "이름"으로 조회한다. 호출측이 이미 이름을 알고 있으면
    (위치기반 검색 결과에 들어 있다) 함께 넘겨서 B의 상세조회를 생략시킨다 -
    관광지 1곳당 API 호출이 2회에서 1회로 줄어든다.
    """

    content_id: str
    name: str | None = None


class Congestion(BaseModel):
    content_id: str
    name: str
    daily: list[DayRate]
    has_data: bool  # False = 정상 응답이지만 데이터 없음. API 실패와 다르다.


class PlanItem(BaseModel):
    content_id: str
    name: str
    order: int
    visit_time: str  # "HH:MM"
    note: str | None = None  # 사용자에게 보여줄 설명. LLM이 덮어쓸 수 있다.

    # 집중률은 note와 분리해서 둔다. note는 LLM 설명으로 덮이기 때문에,
    # 여기에 같이 담아두면 재추천 판단 근거가 사라진다.
    congestion_label: str | None = None
    high_congestion: bool = False

    # 최종 일정에 뽑힌 장소만 상세정보(소개문/운영시간/휴무일)를 조회해 붙인다.
    # 후보 전체를 상세조회하면 관광지당 API 호출 2회가 후보 수만큼 늘어난다.
    detail: Place | None = None


class Plan(BaseModel):
    title: str
    travel_date: str  # "YYYYMMDD"
    items: list[PlanItem]
    summary: str


class PlanRequest(BaseModel):
    map_x: float
    map_y: float
    travel_date: str
    start_time: str  # "HH:MM"
    end_time: str  # "HH:MM"
    place_count: int
    theme: str | None = None


class SavedPlan(BaseModel):
    plan_id: int
    title: str
    travel_date: str
    items: list[PlanItem]


class LocationReq(BaseModel):
    map_x: float
    map_y: float
    # 검색 반경(m). 기본값을 계약에서 한 번만 정해야 제주 추천 탭과 코스 생성이
    # 같은 범위의 관광지를 본다 - 호출측은 반경을 보내지 않는다.
    # 1km로는 지역당 후보가 0~3곳뿐이라 일정이 항상 같게 나왔고, 5km면 11~20곳.
    radius: int = 5000


class SavePlanRequest(BaseModel):
    title: str
    travel_date: str
    items: list[PlanItem]


class ReplanRequest(BaseModel):
    plan: Plan
    target_content_id: str
    reason: str


class ReplanResponse(BaseModel):
    plan: Plan
    replaced_content_id: str
    replacement_reason: str


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


# 공통 에러 코드. 사용자에게 내부 예외를 그대로 노출하지 않기 위해
# A/B/C/D가 동일한 코드 집합을 사용한다 (A_backend_auth.md 7절).
class ErrorCode:
    NOT_FOUND = "NOT_FOUND"
    EMPTY_RESULT = "EMPTY_RESULT"  # 성공 + 결과 0개 (에러 아님, 참고용 상수)
    NO_CONGESTION_DATA = "NO_CONGESTION_DATA"  # 성공 + 집중률 데이터 없음
    UPSTREAM_TIMEOUT = "UPSTREAM_TIMEOUT"
    UPSTREAM_ERROR = "UPSTREAM_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    DUPLICATE_USER = "DUPLICATE_USER"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    LLM_INVALID_OUTPUT = "LLM_INVALID_OUTPUT"
    NO_REPLACEMENT_CANDIDATE = "NO_REPLACEMENT_CANDIDATE"
