"""비밀번호 해시 (A_backend_auth.md 3절: 평문 저장 금지).

외부 의존성(passlib/bcrypt) 없이 표준 라이브러리 hashlib.pbkdf2_hmac만으로
구현한다. 운영 환경에서 더 강한 알고리즘(argon2/bcrypt)이 필요하면 이
파일만 교체하면 된다 - 호출부(auth.py)는 hash_password/verify_password
시그니처만 알면 된다.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

_ITERATIONS = 260_000
_ALGO = "sha256"


def hash_password(plain_password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(_ALGO, plain_password.encode("utf-8"), bytes.fromhex(salt), _ITERATIONS)
    return f"{_ALGO}${_ITERATIONS}${salt}${digest.hex()}"


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        algo, iterations_str, salt, expected_hex = password_hash.split("$")
        iterations = int(iterations_str)
    except (ValueError, AttributeError):
        return False

    digest = hashlib.pbkdf2_hmac(algo, plain_password.encode("utf-8"), bytes.fromhex(salt), iterations)
    return hmac.compare_digest(digest.hex(), expected_hex)
