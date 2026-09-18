-- =============================================================================
-- 어디GO 테이블 정의 (MySQL 8.0+ / Amazon RDS for MySQL)
--
-- 애플리케이션 코드에는 DDL이 없다. 테이블은 이 파일로만 만든다.
-- 앱 계정(eodiegoServer)은 SELECT, INSERT 권한만 가지므로 테이블을 만들거나
-- 바꿀 수 없다 - 관리자 계정으로 이 파일을 실행한다.
--
-- 이 파일은 "현재 선택된 데이터베이스"에 테이블을 만든다 (재실행해도 안전).
--   mysql -u <관리자> -p <DB이름> < db/schema.sql
-- 처음 환경을 만들 때는 db/setup_local.sql 이 DB 생성 + 이 파일 + 앱 계정 생성을 한 번에 한다.
--
-- 설계 원칙: 앱 계정에 UPDATE/DELETE가 없으므로 모든 기록은 "추가만" 한다.
--   - 로그아웃   : session 을 지우지 않고 session_revocation 에 폐기 기록을 추가
--   - 일정 삭제  : plan 을 지우지 않고 plan_deletion 에 삭제 기록을 추가
--   - 호출 카운터: 숫자를 +1 하지 않고 호출 1건당 1행을 추가한 뒤 COUNT 로 센다
-- 만료된 세션 등 오래된 기록 정리는 관리자가 db/maintenance.sql 로 한다.
--
-- 시각 컬럼 중 앱이 비교에 쓰는 값(expires_at, *_day)은 앱이 직접 넣는다.
-- created_at 류는 DB 기본값(서버 시간대, RDS 기본 UTC)이며 기록용이다.
-- =============================================================================

-- --- A: 회원 -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `user` (
    `user_id`       BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `username`      VARCHAR(100)    NOT NULL,
    `password_hash` VARCHAR(255)    NOT NULL,  -- PBKDF2 해시 (평문 저장 금지)
    `created_at`    DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (`user_id`),
    UNIQUE KEY `uq_user_username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --- A: 세션 (토큰 원문이 아니라 SHA-256 해시만 저장) ------------------------------
CREATE TABLE IF NOT EXISTS `session` (
    `token_hash` CHAR(64)        NOT NULL,
    `user_id`    BIGINT UNSIGNED NOT NULL,
    `expires_at` DATETIME(6)     NOT NULL,  -- UTC, 앱이 넣음
    `created_at` DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (`token_hash`),
    KEY `idx_session_user` (`user_id`),
    KEY `idx_session_expires` (`expires_at`),
    CONSTRAINT `fk_session_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 로그아웃 기록. 여기 있는 세션은 만료 전이라도 무효다.
CREATE TABLE IF NOT EXISTS `session_revocation` (
    `token_hash` CHAR(64)    NOT NULL,
    `revoked_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (`token_hash`),
    CONSTRAINT `fk_revocation_session` FOREIGN KEY (`token_hash`) REFERENCES `session` (`token_hash`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --- A: 저장 일정 (관광공사 상세정보는 저장하지 않고 content_id만 참조) ---------------
CREATE TABLE IF NOT EXISTS `plan` (
    `plan_id`     BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `user_id`     BIGINT UNSIGNED NOT NULL,
    `title`       VARCHAR(200)    NOT NULL,
    `travel_date` CHAR(8)         NOT NULL,  -- YYYYMMDD
    `created_at`  DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (`plan_id`),
    KEY `idx_plan_user` (`user_id`, `created_at`),
    CONSTRAINT `fk_plan_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `plan_item` (
    `plan_item_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `plan_id`      BIGINT UNSIGNED NOT NULL,
    `content_id`   VARCHAR(20)     NOT NULL,
    `name`         VARCHAR(200)    NOT NULL,
    `item_order`   INT             NOT NULL,  -- ORDER는 예약어라 이름을 바꿨다
    `visit_time`   CHAR(5)         NOT NULL,  -- HH:MM
    `note`         TEXT            NULL,
    PRIMARY KEY (`plan_item_id`),
    KEY `idx_plan_item_plan` (`plan_id`, `item_order`),
    CONSTRAINT `fk_plan_item_plan` FOREIGN KEY (`plan_id`) REFERENCES `plan` (`plan_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 일정 삭제 기록. 여기 있는 일정은 조회에서 제외된다.
CREATE TABLE IF NOT EXISTS `plan_deletion` (
    `plan_id`    BIGINT UNSIGNED NOT NULL,
    `user_id`    BIGINT UNSIGNED NOT NULL,
    `deleted_at` DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (`plan_id`),
    CONSTRAINT `fk_plan_deletion_plan` FOREIGN KEY (`plan_id`) REFERENCES `plan` (`plan_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --- B: 관광공사 API 호출 기록 (일일 한도 관리, 호출 1건 = 1행) ---------------------
CREATE TABLE IF NOT EXISTS `kto_api_call` (
    `call_id`   BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `call_day`  DATE            NOT NULL,  -- 한국 시간 기준 날짜, 앱이 넣음
    `operation` VARCHAR(50)     NOT NULL,
    `called_at` DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (`call_id`),
    KEY `idx_kto_call_day` (`call_day`, `operation`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --- C: LLM 요청 기록 (하루 요청 상한 관리, 요청 1건 = 1행) -------------------------
CREATE TABLE IF NOT EXISTS `llm_request` (
    `request_id`   BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `request_day`  DATE            NOT NULL,  -- UTC 기준 날짜, 앱이 넣음
    `model`        VARCHAR(100)    NOT NULL,
    `requested_at` DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (`request_id`),
    KEY `idx_llm_request_day` (`request_day`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- LLM 응답의 토큰 사용량 (응답 1건 = 1행)
CREATE TABLE IF NOT EXISTS `llm_token_usage` (
    `usage_id`      BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `usage_day`     DATE            NOT NULL,  -- UTC 기준 날짜, 앱이 넣음
    `model`         VARCHAR(100)    NOT NULL,
    `input_tokens`  INT UNSIGNED    NOT NULL,
    `output_tokens` INT UNSIGNED    NOT NULL,
    `recorded_at`   DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (`usage_id`),
    KEY `idx_llm_token_usage_day` (`usage_day`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
