"""B 설정.

서비스키/URL은 전부 환경변수로만 관리한다 (하드코딩 금지, B_openapi.md 1절).
USE_MOCK=true(기본값)면 실제 한국관광공사 API를 호출하지 않고 mock 데이터를
반환한다. 실제 연동 시 USE_MOCK=false + KTO_SERVICE_KEY 를 설정한다.
"""

from __future__ import annotations

import os
from urllib.parse import unquote


def _service_key(raw: str) -> str:
    """공공데이터포털은 같은 키를 Encoding/Decoding 두 형태로 준다.

    Encoding 키("...%2F...%3D%3D")를 그대로 httpx params에 넘기면 '%'가 한 번
    더 인코딩돼("%252F") 인증에 실패한다. 반대로 Decoding 키를 넘기면 httpx가
    알아서 인코딩해준다. 어느 쪽을 .env에 넣어도 되도록 여기서 한 번 푼다.
    """

    return unquote(raw) if "%" in raw else raw


def _bool_env(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


USE_MOCK: bool = _bool_env("USE_MOCK", True)

KTO_SERVICE_KEY: str = _service_key(os.environ.get("KTO_SERVICE_KEY", ""))
# 국문 관광정보 서비스 (팀 확정 endpoint).
KTO_BASE_URL: str = os.environ.get(
    "KTO_BASE_URL", "https://apis.data.go.kr/B551011/KorService2"
)
# 관광지 예측 집중률 서비스 (팀 확정 endpoint).
# 세부 operation 이름/파라미터는 실제 API 명세를 받는 대로 client.py의
# TODO 부분을 채운다.
KTO_CONGESTION_BASE_URL: str = os.environ.get(
    "KTO_CONGESTION_BASE_URL", "https://apis.data.go.kr/B551011/TatsCnctrRateService"
)

# 위치기반 검색으로 가져올 콘텐츠 유형 (12=관광지, 14=문화시설, 39=음식점...).
# 비워두면 전체 유형을 가져오는데, 실제로 해보면 제주시청 주변 10건이 전부
# 음식점/쇼핑으로 채워지고 예측 집중률 API(관광지 전용)와 1/10만 매칭된다.
# 12로 좁히면 6/10까지 올라간다. 유형을 바꾸려면 .env에서만 조정한다.
KTO_CONTENT_TYPE_ID: str = os.environ.get("KTO_CONTENT_TYPE_ID", "12").strip()

# 상세정보 일괄 조회 상한. 관광지 1곳당 API 2회(공통정보+소개정보)가 나가므로
# 일정 한 개에 들어갈 수 있는 수준으로 막아둔다.
MAX_DETAIL_BATCH: int = int(os.environ.get("MAX_DETAIL_BATCH", "10"))

# 위치기반 검색 한 번에 받아올 건수. 지정하지 않으면 API 기본값(10건)이라
# 반경을 넓혀도 후보가 늘지 않는다.
KTO_NUM_OF_ROWS: int = int(os.environ.get("KTO_NUM_OF_ROWS", "20"))

# 공공데이터포털 일일 호출 한도. 0이면 한도 추적을 끈다.
# 실제 한도는 발급받은 계정 등급에 따라 다르므로 .env에서 맞춘다.
KTO_DAILY_QUOTA: int = int(os.environ.get("KTO_DAILY_QUOTA", "1000"))

# 호출 횟수는 MySQL(kto_api_call)에 남긴다. 접속 정보는 shared/database.py 가
# .env 에서 읽는다.

REQUEST_TIMEOUT_SECONDS: float = float(os.environ.get("KTO_TIMEOUT_SECONDS", "5"))
MAX_RETRY: int = int(os.environ.get("KTO_MAX_RETRY", "1"))

# 관광공사 API에 동시에 열어둘 연결 수. 병렬 조회를 하되 상대 서버를
# 과하게 두드리지 않도록 제한한다.
MAX_CONCURRENT_UPSTREAM: int = int(os.environ.get("KTO_MAX_CONCURRENCY", "10"))

# 집중률 API 한 번 호출로 받아올 행(날짜) 수. 응답은 날짜별로 한 행씩 온다
# (baseYmd/cnctrRate). travel_date가 예측 가능 범위를 벗어나지 않도록
# 충분히 넉넉하게 잡는다.
CONGESTION_NUM_OF_ROWS: int = int(os.environ.get("CONGESTION_NUM_OF_ROWS", "30"))

# 위치기반 검색 후보를 몇 개까지 상세/집중률 조회로 넘길지 (B_openapi.md 5절).
MAX_CANDIDATES_FOR_CONGESTION: int = int(os.environ.get("MAX_CANDIDATES", "20"))

HOST: str = os.environ.get("B_HOST", "0.0.0.0")
PORT: int = int(os.environ.get("B_PORT", "8001"))
