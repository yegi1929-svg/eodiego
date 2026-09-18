"""테스트 보조 함수 (운영 코드에서는 쓰지 않는다).

앱 계정은 DELETE 권한이 없어 테스트가 남긴 데이터를 지울 수 없다. 아이디와
날짜를 테스트마다 고유하게 만들어 실행 간에 서로 섞이지 않게 한다.
"""

from __future__ import annotations

import random
import uuid
from datetime import date, timedelta


def make_unique_name(prefix: str = "t") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def make_unique_day() -> date:
    """다른 테스트/다른 실행과 겹치지 않는 먼 미래 날짜 (날짜별 카운터 격리용)."""

    return date(2100, 1, 1) + timedelta(days=random.randint(0, 2_500_000))
