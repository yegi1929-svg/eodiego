"""C 테스트 공통 설정.

- 실제 OpenAI API를 절대 부르지 않게 USE_LLM을 끈다. 계정 한도가 하루 50회라
  테스트가 실제 호출을 하면 그대로 한도가 깎인다.
- LLM 사용량은 날짜별로 센다. 앱 계정은 DELETE 권한이 없어 테스트 기록을 지울 수
  없으므로, 테스트마다 고유한 먼 미래 날짜로 기록해 섞이지 않게 한다.
"""

import pytest

from C_ai_planner import config, llm_client, llm_usage
from shared.testing import make_unique_day


@pytest.fixture(autouse=True)
def isolate_llm(monkeypatch):
    monkeypatch.setattr(config, "USE_LLM", False)
    monkeypatch.setattr(llm_client, "_openai_client", None)
    day = make_unique_day()
    monkeypatch.setattr(llm_usage, "_today", lambda: day)
    return day
