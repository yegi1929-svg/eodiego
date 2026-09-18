"""C 설정 (C_ai_planner.md 5절)."""

from __future__ import annotations

import os

# 선택 날짜의 예측 집중률이 이 값 이상이면 재추천 대상으로 표시한다.
# 실시간 혼잡을 의미하지 않는다 - 어디까지나 "예측" 값에 대한 임계치다.
# 실제 값은 팀과 협의해서 조정한다.
CONGESTION_THRESHOLD: float = float(os.environ.get("CONGESTION_THRESHOLD", "70.0"))

# 재추천 후보를 찾을 때 기존 관광지 대비 허용하는 최대 추가 이동거리(m).
MAX_REPLAN_DISTANCE_DELTA_M: float = float(os.environ.get("MAX_REPLAN_DISTANCE_DELTA_M", "3000"))

# 방문지 1곳당 기본 체류시간(분). Place.expected_stay_minutes가 없을 때 사용.
DEFAULT_STAY_MINUTES: int = int(os.environ.get("DEFAULT_STAY_MINUTES", "60"))

B_BASE_URL: str = os.environ.get("B_BASE_URL", "http://localhost:8001")
REQUEST_TIMEOUT_SECONDS: float = float(os.environ.get("B_TIMEOUT_SECONDS", "5"))

USE_LLM: bool = os.environ.get("USE_LLM", "false").strip().lower() in {"1", "true", "yes"}
LLM_API_KEY: str = os.environ.get("LLM_API_KEY", "")  # OpenAI API 키
LLM_TIMEOUT_SECONDS: float = float(os.environ.get("LLM_TIMEOUT_SECONDS", "8"))

# OpenAI 모델. 발급받은 계정에서 쓸 수 있는 모델로 맞춘다.
LLM_MODEL: str = os.environ.get("LLM_MODEL", "gpt-5.4-mini")
# 짧은 문장 생성이라 추론이 필요 없다. 추론 토큰은 출력 토큰으로 과금된다.
LLM_REASONING_EFFORT: str = os.environ.get("LLM_REASONING_EFFORT", "none")
# 추론 토큰도 이 상한에 포함되므로 너무 낮추면 답이 잘려 기본 문구로 떨어진다.
LLM_MAX_OUTPUT_TOKENS: int = int(os.environ.get("LLM_MAX_OUTPUT_TOKENS", "1500"))

# 계정 한도가 50 RPD(하루 요청 수)라서, 초과해 429를 받기 전에 우리가 먼저 멈춘다.
# 나머지는 수동 확인/시연용 여유분. 0이면 상한을 두지 않는다.
LLM_DAILY_REQUEST_LIMIT: int = int(os.environ.get("LLM_DAILY_REQUEST_LIMIT", "45"))
# SDK 자동 재시도도 요청 1회로 세어져 하루 한도를 깎는다 - 기본은 재시도 없음.
LLM_MAX_RETRIES: int = int(os.environ.get("LLM_MAX_RETRIES", "0"))

# 근거 자료로 넣는 관광지 소개문 길이 상한(자). 입력 토큰 대부분이 소개문이다.
LLM_OVERVIEW_MAX_CHARS: int = int(os.environ.get("LLM_OVERVIEW_MAX_CHARS", "400"))

# LLM 요청 수/토큰 사용량은 MySQL(llm_request, llm_token_usage)에 남긴다.
# 접속 정보는 shared/database.py 가 .env 에서 읽는다.

HOST: str = os.environ.get("C_HOST", "0.0.0.0")
PORT: int = int(os.environ.get("C_PORT", "8002"))
