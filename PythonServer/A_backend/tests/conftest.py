import pytest
from fastapi.testclient import TestClient

from A_backend import main


@pytest.fixture
def client(mysql_db):
    # 테이블은 db/schema.sql 로 만들어져 있어야 한다 (앱은 DDL을 하지 않는다).
    return TestClient(main.app)
