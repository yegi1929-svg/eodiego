-- =============================================================================
-- 오래된 기록 정리 (관리자 계정으로 실행, 앱 계정은 DELETE 권한이 없다)
--
-- 앱은 기록을 "추가만" 하므로 만료된 세션과 오래된 호출 기록이 쌓인다.
-- 주기적으로(예: 하루 한 번) 실행한다.
--
--   mysql -u <관리자> -p eodiego < db/maintenance.sql
-- =============================================================================

-- 만료된 세션 (폐기 기록이 먼저 참조하므로 폐기 기록부터 지운다)
DELETE r FROM `session_revocation` r
JOIN `session` s ON s.token_hash = r.token_hash
WHERE s.expires_at < UTC_TIMESTAMP(6);

DELETE FROM `session` WHERE `expires_at` < UTC_TIMESTAMP(6);

-- 한도 관리용 호출 기록은 최근 90일만 남긴다
DELETE FROM `kto_api_call`    WHERE `call_day`    < CURRENT_DATE - INTERVAL 90 DAY;
DELETE FROM `llm_request`     WHERE `request_day` < CURRENT_DATE - INTERVAL 90 DAY;
DELETE FROM `llm_token_usage` WHERE `usage_day`   < CURRENT_DATE - INTERVAL 90 DAY;
