"""B_openapi.md 11절 회귀 테스트: "보덕사(제주)" -> "보덕사" 매칭 고정."""

from B_openapi.matching import build_signgu_cd, extract_base_name, match_congestion_candidate


def test_extract_base_name_strips_parenthesis():
    assert extract_base_name("보덕사(제주)") == "보덕사"


def test_extract_base_name_no_parenthesis():
    assert extract_base_name("성산일출봉") == "성산일출봉"


def test_build_signgu_cd_combines_area_and_dong():
    assert build_signgu_cd("50", "110") == "50110"


def test_match_single_candidate_used():
    candidates = [{"name": "보덕사"}]
    assert match_congestion_candidate(candidates, "보덕사") == candidates[0]


def test_match_multiple_prefers_exact_name():
    candidates = [{"name": "보덕사", "id": 1}, {"name": "보덕사X", "id": 2}]
    assert match_congestion_candidate(candidates, "보덕사")["id"] == 1


def test_match_ambiguous_returns_none_same_name_different_region():
    # 동일 이름의 타지역 관광지가 섞여 들어온 경우 (필터가 완벽하지 않았던 상황)
    candidates = [{"name": "보덕사"}, {"name": "보덕사"}]
    assert match_congestion_candidate(candidates, "보덕사") is None


def test_match_no_candidates_returns_none():
    assert match_congestion_candidate([], "보덕사") is None
