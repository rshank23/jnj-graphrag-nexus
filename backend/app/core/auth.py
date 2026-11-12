"""API-key / role authentication with optional Microsoft Entra ID (Azure AD) JWT validation.

Roles: ``commercial`` (promotional users; off-label content is withheld), ``medical`` (Medical Affairs / MSL),
``mlr`` (reviewers; may record decisions) and ``admin`` (key management, audit). With ``NEXUS_REQUIRE_API_KEY=false``
(the default for the local POC) requests run as an anonymous ``medical`` user and the ``X-Nexus-Role`` header may set the role.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from fastapi import Depends, Header, HTTPException, status

from app.config import get_settings
from app.core.db import get_db, sha256, utcnow
from app.core.telemetry import current_actor, current_role

ROLES = ("commercial", "medical", "mlr", "admin")


@dataclass
class Principal:
    name: str
    role: str
    tier: str = "standard"
    monthly_limit: int = 10000
    authenticated: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "role": self.role, "tier": self.tier, "authenticated": self.authenticated}


def create_api_key(name: str, role: str, tier: str = "standard", monthly_limit: int = 10000) -> Dict[str, Any]:
    if role not in ROLES:
        raise ValueError(f"role must be one of {ROLES}")
    key = "nxs_" + secrets.token_urlsafe(24)
    get_db().execute("INSERT INTO api_keys (key_hash, name, role, tier, monthly_limit, created) VALUES (?,?,?,?,?,?)",
                     (sha256(key), name, role, tier, monthly_limit, utcnow()))
    get_db().audit("auth.key_created", name, {"role": role, "tier": tier}, "admin")
    return {"api_key": key, "name": name, "role": role, "tier": tier, "monthly_limit": monthly_limit}


def list_api_keys() -> List[Dict[str, Any]]:
    return get_db().query("SELECT substr(key_hash,1,10) key_prefix, name, role, tier, monthly_limit, created, revoked FROM api_keys")


def ensure_bootstrap_key() -> None:
    key = get_settings().bootstrap_admin_key
    if key and not get_db().query("SELECT 1 FROM api_keys WHERE key_hash=?", (sha256(key),)):
        get_db().execute("INSERT INTO api_keys (key_hash, name, role, tier, monthly_limit, created) VALUES (?,?,?,?,?,?)",
                         (sha256(key), "bootstrap-admin", "admin", "internal", 10 ** 9, utcnow()))


def _from_api_key(key: str) -> Optional[Principal]:
    rows = get_db().query("SELECT name, role, tier, monthly_limit, revoked FROM api_keys WHERE key_hash=?", (sha256(key),))
    if not rows or rows[0]["revoked"]:
        return None
    r = rows[0]
    return Principal(r["name"], r["role"], r["tier"], r["monthly_limit"], True)


def _from_entra(token: str) -> Optional[Principal]:  # pragma: no cover - requires a tenant
    s = get_settings()
    if not s.entra_tenant_id:
        return None
    try:
        import jwt  # type: ignore
        from jwt import PyJWKClient  # type: ignore

        jwks = PyJWKClient(f"https://login.microsoftonline.com/{s.entra_tenant_id}/discovery/v2.0/keys")
        claims = jwt.decode(token, jwks.get_signing_key_from_jwt(token).key, algorithms=["RS256"], audience=s.entra_audience,
                            issuer=f"https://login.microsoftonline.com/{s.entra_tenant_id}/v2.0")
    except Exception:
        return None
    roles = [r for r in claims.get("roles", []) if r in ROLES]
    return Principal(claims.get("preferred_username") or claims.get("oid", "entra-user"), roles[0] if roles else "commercial", authenticated=True)


def resolve_principal(api_key: Optional[str], authorization: Optional[str], role_header: Optional[str]) -> Principal:
    settings = get_settings()
    principal: Optional[Principal] = None
    if api_key:
        principal = _from_api_key(api_key)
        if principal is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or revoked API key")
    elif authorization and authorization.lower().startswith("bearer "):
        principal = _from_entra(authorization.split(" ", 1)[1])
        if principal is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid bearer token")
    if principal is None:
        if settings.require_api_key:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "API key required (X-Nexus-API-Key)")
        role = role_header if role_header in ROLES else "medical"
        principal = Principal("anonymous", role)
    if principal.authenticated and get_db().monthly_calls(principal.name) >= principal.monthly_limit:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, f"Monthly quota of {principal.monthly_limit} calls exceeded")
    current_actor.set(principal.name)
    current_role.set(principal.role)
    return principal


def get_principal(x_nexus_api_key: Optional[str] = Header(default=None), authorization: Optional[str] = Header(default=None),
                  x_nexus_role: Optional[str] = Header(default=None)) -> Principal:
    return resolve_principal(x_nexus_api_key, authorization, x_nexus_role)


def require_role(*roles: str):
    def dep(principal: Principal = Depends(get_principal)) -> Principal:
        if principal.role not in roles and principal.role != "admin":
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Role '{principal.role}' not permitted; requires one of {roles}")
        return principal
    return dep
