"""일정 생성/재추천은 C, 저장/조회/삭제는 A. D는 둘 다 프록시만 한다."""

from __future__ import annotations

from .. import config
from . import _http


async def generate_plan(plan_request: dict) -> dict:
    resp = await _http.request("C", config.C_BASE_URL, "POST", "/plan/generate", json=plan_request)
    return resp.json()


async def replan(replan_request: dict) -> dict:
    resp = await _http.request("C", config.C_BASE_URL, "POST", "/plan/replan", json=replan_request)
    return resp.json()


def _auth_cookies(session_token: str | None) -> dict | None:
    return {config.SESSION_COOKIE_NAME: session_token} if session_token else None


async def save_plan(session_token: str | None, save_request: dict) -> dict:
    resp = await _http.request(
        "A", config.A_BASE_URL, "POST", "/plans", json=save_request, cookies=_auth_cookies(session_token)
    )
    return resp.json()


async def list_plans(session_token: str | None) -> list[dict]:
    resp = await _http.request("A", config.A_BASE_URL, "GET", "/plans", cookies=_auth_cookies(session_token))
    return resp.json()


async def get_plan_detail(session_token: str | None, plan_id: int) -> dict:
    resp = await _http.request(
        "A", config.A_BASE_URL, "GET", f"/plans/{plan_id}", cookies=_auth_cookies(session_token)
    )
    return resp.json()


async def delete_plan(session_token: str | None, plan_id: int) -> None:
    await _http.request("A", config.A_BASE_URL, "DELETE", f"/plans/{plan_id}", cookies=_auth_cookies(session_token))
