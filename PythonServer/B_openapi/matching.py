"""관광지 이름 <-> 집중률 API 매칭 로직 (B_openapi.md 3절).

위치기반 검색 결과의 title="보덕사(제주)" 같은 표기에서 괄호 앞부분만
추출하고, 지역 코드와 결합해 집중률 API를 조회한다. 이름만으로 전역
매칭하지 않는다 (동명 관광지가 다른 지역에 있을 수 있음).
"""

from __future__ import annotations

import re

_PAREN_SUFFIX_RE = re.compile(r"\s*\([^)]*\)\s*$")


def extract_base_name(title: str) -> str:
    """"보덕사(제주)" -> "보덕사". 괄호가 없으면 그대로 반환한다."""

    return _PAREN_SUFFIX_RE.sub("", title).strip()


def build_signgu_cd(area_cd: str, l_dong_signgu_cd: str) -> str:
    """areaCd="50" + lDongSignguCd="110" -> signguCd="50110".

    실제 조합 규칙은 한국관광공사 지역코드 체계를 따른다. 규칙이 문서와
    다르게 확인되면 이 함수 한 곳만 수정하면 되도록 로직을 격리했다.
    """

    return f"{area_cd}{l_dong_signgu_cd}"


def match_congestion_candidate(
    candidates: list[dict], exact_name: str
) -> dict | None:
    """집중률 API 후보 목록에서 매칭 규칙(B_openapi.md 3절)을 적용한다.

    candidates: 집중률 API가 tAtsNm/areaCd/signguCd 조회로 반환한 원본 목록.
                각 dict는 최소 "name" 키를 가진다고 가정.

    규칙:
      1. 이름 + 지역 코드로 이미 필터링된 상태로 들어온다고 가정한다.
      2. 응답이 1개면 그것을 사용한다.
      3. 여러 개면 정확한 이름이 일치하는 것을 우선한다.
      4. 그래도 불명확하면(정확히 일치하는 게 0개 또는 2개 이상) None을
         반환한다 -> 호출측은 해당 관광지의 집중률을 사용하지 않는다.
    """

    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    exact_matches = [c for c in candidates if c.get("name") == exact_name]
    if len(exact_matches) == 1:
        return exact_matches[0]

    # 여러 개거나 하나도 없으면 불명확 -> 사용하지 않는다.
    return None
