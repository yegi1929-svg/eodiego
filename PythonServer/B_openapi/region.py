"""동/서 구역 분류 (B_openapi.md 10절).

판정 기준을 이 파일 한 곳에서만 관리한다. 다른 파일에 하드코딩된 지역
판단 로직을 두지 않는다.

기준: 제주도 기준 경도(map_x) 126.53을 동/서 경계로 삼는다.
      126.53 미만 -> "서", 이상 -> "동".
예외 지역(EXCEPTION_CONTENT_IDS)은 경계선 근처에 있어 수동으로 지정한다.
실제 서비스 지역이 제주가 아니라면 BOUNDARY_LONGITUDE 값을 팀과 협의해
교체한다.
"""

from __future__ import annotations

from shared.schemas import Region

BOUNDARY_LONGITUDE: float = 126.53

# 화면의 지역 선택지와 위치기반 검색에 쓸 대표 좌표.
# 화면(D_frontend/eodiego)이 좌표를 하드코딩하지 않도록 여기서만 관리한다.
# 다른 지역을 추가/삭제하려면 이 목록만 고치면 된다.
SEARCH_REGIONS: list[Region] = [
    Region(code="jeju-si", name="제주시", map_x=126.5312, map_y=33.4996),
    Region(code="seogwipo", name="서귀포", map_x=126.5644, map_y=33.2541),
    Region(code="east", name="서귀 동쪽", map_x=126.9425, map_y=33.4587),
    Region(code="west", name="제주 서쪽", map_x=126.2396, map_y=33.3937),
]


def list_regions() -> list[Region]:
    """화면이 지역 칩으로 그릴 선택지 목록."""

    return list(SEARCH_REGIONS)

# content_id -> "동"/"서" 로 수동 고정하는 예외 지역.
# 예: 경계선에 걸쳐 있어 좌표만으로는 잘못 분류되는 관광지.
EXCEPTION_CONTENT_IDS: dict[str, str] = {}


def classify_region(place) -> str:
    """place(.content_id, .map_x 속성을 가진 객체 또는 dict)를 "동"/"서"로 분류."""

    content_id = place.get("content_id") if isinstance(place, dict) else place.content_id
    if content_id in EXCEPTION_CONTENT_IDS:
        return EXCEPTION_CONTENT_IDS[content_id]

    map_x = place.get("map_x") if isinstance(place, dict) else place.map_x
    return "서" if map_x < BOUNDARY_LONGITUDE else "동"
