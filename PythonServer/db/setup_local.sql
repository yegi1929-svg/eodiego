-- =============================================================================
-- 로컬 개발 환경 한 번에 만들기 (관리자 계정으로, 프로젝트 루트에서 실행)
--
--   운영 DB  eodiego       : 서버(run_local.sh)가 쓰는 DB
--   테스트 DB eodiego_test : pytest가 쓰는 DB (운영 데이터를 건드리지 않게 분리)
--
-- 두 DB에 같은 schema.sql 을 적용하고, 앱 계정에 두 DB의 SELECT/INSERT만 준다.
-- source 경로는 mysql 클라이언트를 실행한 위치 기준이라 반드시 프로젝트 루트에서 실행한다.
--
--   mysql -u root -p -e "SET @app_password='<.env의 DB_PASSWORD>'; source db/setup_local.sql"
-- =============================================================================

CREATE DATABASE IF NOT EXISTS `eodiego` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE `eodiego`;
source db/schema.sql

CREATE DATABASE IF NOT EXISTS `eodiego_test` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE `eodiego_test`;
source db/schema.sql

SET @app_database = 'eodiego';
source db/create_app_user.sql

SET @app_database = 'eodiego_test';
source db/create_app_user.sql
