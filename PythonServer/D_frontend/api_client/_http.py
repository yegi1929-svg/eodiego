"""A/B/C 호출 공통 헬퍼. 화면 코드(=이 서버의 main.py) 안에 fetch/httpx
호출을 직접 여러 번 흩어놓지 않기 위해 api_client 모듈로 분리했다
(D_frontend.md 12절의 "src/api/*.js 분리"를 서버 쪽에서 동일하게 적용)."""

from __future__ import annotations

import httpx

from .. import config
from .errors import UpstreamRejectedError, UpstreamUnavailableError


async def request(
    service: str,
    base_url: str,
    method: str,
    path: str,
    *,
    json: dict | None = None,
    cookies: dict | None = None,
) -> httpx.Response:
    try:
        async with httpx.AsyncClient(base_url=base_url, timeout=config.REQUEST_TIMEOUT_SECONDS) as client:
            resp = await client.request(method, path, json=json, cookies=cookies)
    except httpx.TimeoutException as exc:
        raise UpstreamUnavailableError(service, f"{service} 서비스 응답 지연") from exc
    except httpx.HTTPError as exc:
        raise UpstreamUnavailableError(service, f"{service} 서비스 연결 실패") from exc

    if resp.status_code >= 400:
        code, message = "UPSTREAM_ERROR", f"{service} 서비스 오류"
        try:
            body = resp.json()
            err = body.get("error", body.get("detail", {}).get("error") if isinstance(body.get("detail"), dict) else None)
            if err:
                code, message = err.get("code", code), err.get("message", message)
        except ValueError:
            pass
        raise UpstreamRejectedError(service, resp.status_code, code, message)

    return resp
