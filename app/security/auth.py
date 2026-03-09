from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import jwt

from app.errors import AuthError


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    email: Optional[str]
    name: Optional[str]
    claims: Dict[str, Any]


def parse_bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise AuthError("missing authorization header")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthError("invalid authorization format")
    return parts[1]


def decode_docfoundry_jwt(token: str, *, secret: str, algorithm: str = "HS256") -> AuthContext:
    try:
        claims = jwt.decode(token, secret, algorithms=[algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("token expired") from exc
    except Exception as exc:
        raise AuthError("invalid token") from exc

    sub = claims.get("sub")
    if not isinstance(sub, str) or not sub.strip():
        raise AuthError("invalid token subject")

    email = claims.get("email") if isinstance(claims.get("email"), str) else None
    name = claims.get("name") if isinstance(claims.get("name"), str) else None
    return AuthContext(user_id=sub, email=email, name=name, claims=claims)
