"""DB 접속 설정과 앱 계정 권한 검증.

앱 계정(eodiegoServer)은 SELECT, INSERT만 할 수 있어야 한다. DDL, UPDATE,
DELETE가 막혀 있는지 실제 MySQL에 시도해서 확인한다.
"""

import pymysql
import pytest

from shared import database


def test_missing_env_raises_clear_config_error(monkeypatch):
    monkeypatch.delenv("DB_PASSWORD", raising=False)
    with pytest.raises(database.DatabaseConfigError) as exc:
        database.connection_settings()
    assert "DB_PASSWORD" in str(exc.value)


def test_no_hardcoded_defaults_for_credentials(monkeypatch):
    for key in ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(database.DatabaseConfigError) as exc:
        database.connection_settings()
    for key in ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD"):
        assert key in str(exc.value)


def test_ssl_ca_is_optional(monkeypatch):
    monkeypatch.setenv("DB_SSL_CA", "/path/rds-ca.pem")
    assert database.connection_settings()["ssl"] == {"ca": "/path/rds-ca.pem"}


@pytest.mark.parametrize(
    "statement",
    [
        "CREATE TABLE `t_should_fail` (id INT)",
        "ALTER TABLE `user` ADD COLUMN `x` INT",
        "DROP TABLE `kto_api_call`",
        "UPDATE `user` SET `username` = `username` WHERE 1 = 0",
        "DELETE FROM `session` WHERE 1 = 0",
        "TRUNCATE TABLE `llm_request`",
    ],
)
def test_app_user_cannot_run_ddl_update_or_delete(mysql_db, statement):
    with pytest.raises(pymysql.err.MySQLError) as exc:
        with database.transaction() as cur:
            cur.execute(statement)
    # 1142: command denied to user
    assert exc.value.args[0] in (1142, 1044, 1045)


def test_app_user_can_select_and_insert(mysql_db):
    with database.transaction() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM `user`")
        assert cur.fetchone()["n"] >= 0
        cur.execute("INSERT INTO `kto_api_call` (`call_day`, `operation`) VALUES ('1990-01-01', 'privilege_check')")
        assert cur.rowcount == 1
