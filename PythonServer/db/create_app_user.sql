-- =============================================================================
-- 앱 계정 eodiegoServer 생성 + 권한 부여 (관리자 계정으로 실행)
--
-- 권한은 SELECT, INSERT 뿐이다. 앱은 회원가입/로그인/일정 저장/조회만 할 수 있고
-- CREATE, ALTER, DROP 같은 DDL은 물론 UPDATE, DELETE도 할 수 없다.
--
-- 비밀번호와 DB 이름은 이 파일에 적지 않고 실행할 때 변수로 넘긴다
-- (파일이 저장소에 올라가도 비밀번호가 남지 않게). 앱은 같은 값을 .env 로만 읽는다.
--
--   mysql -u <관리자> -p -e "SET @app_database='eodiego'; SET @app_password='<.env의 DB_PASSWORD>'; source db/create_app_user.sql"
--
-- 재실행해도 안전하다 (이미 있는 계정은 그대로 두고 권한만 다시 부여).
-- 운영(RDS)에서는 '%' 대신 앱 서버 대역으로 호스트를 좁히는 것을 권장한다.
-- =============================================================================

SET @app_user_sql = CONCAT(
    'CREATE USER IF NOT EXISTS ''eodiegoServer''@''%'' IDENTIFIED BY ', QUOTE(@app_password)
);
PREPARE app_user_stmt FROM @app_user_sql;
EXECUTE app_user_stmt;
DEALLOCATE PREPARE app_user_stmt;

SET @app_grant_sql = CONCAT(
    'GRANT SELECT, INSERT ON `', REPLACE(@app_database, '`', '``'), '`.* TO ''eodiegoServer''@''%'''
);
PREPARE app_grant_stmt FROM @app_grant_sql;
EXECUTE app_grant_stmt;
DEALLOCATE PREPARE app_grant_stmt;

SHOW GRANTS FOR 'eodiegoServer'@'%';
