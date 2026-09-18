"""B 테스트 공통 설정.

관광공사 호출 카운터는 날짜별로 센다. 앱 계정은 DELETE 권한이 없어 테스트가
남긴 기록을 지울 수 없으므로, 테스트마다 고유한 먼 미래 날짜로 기록하게 해서
다른 테스트/다른 실행과 섞이지 않게 한다. 실제 오늘 카운터도 오염되지 않는다.
"""

import pytest

from B_openapi import metrics
from shared.testing import make_unique_day


@pytest.fixture(autouse=True)
def isolated_metrics_day(monkeypatch):
    day = make_unique_day()
    monkeypatch.setattr(metrics, "_today", lambda: day)
    return day
