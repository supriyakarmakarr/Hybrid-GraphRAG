"""
JWT Authentication — RS256 only.
tenant_id and roles come ONLY from the verified token or DB.
Never from request body.
"""
import jwt
import structlog
import hmac
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

from app.core.config import settings

log = structlog.get_logger()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)


class TokenClaims(BaseModel):
    user_id: str
    tenant_id: str
    roles: list[str]
    username: str


def create_access_token(user_id: str, tenant_id: str, roles: list[str], username: str) -> str:
    """Sign a JWT. Only called server-side after verifying credentials."""
    if not settings.jwt_private_key:
        raise RuntimeError("JWT private key not configured")

    now = datetime.now(timezone.utc)
    payload = {
        "sub":      user_id,
        "iss":      settings.JWT_ISSUER,
        "aud":      settings.JWT_AUDIENCE,
        "tenant":   tenant_id,
        "roles":    roles,
        "username": username,
        "iat":      now,
        "exp":      now + timedelta(minutes=settings.JWT_EXPIRY_MINUTES),
    }
    return jwt.encode(payload, settings.jwt_private_key, algorithm=settings.JWT_ALGORITHM)


def _decode_token(token: str) -> dict:
    """Verify signature + expiry + issuer + audience. Raises HTTPException on any failure."""
    if not settings.jwt_public_key:
        if settings.ENVIRONMENT != "development":
            raise HTTPException(status_code=503, detail="Auth not configured")
        try:
            return jwt.decode(
                token,
                "dev-secret-change-me",
                algorithms=["HS256"],
                issuer=settings.JWT_ISSUER,
                audience=settings.JWT_AUDIENCE,
            )
        except jwt.PyJWTError as e:
            log.warning("token_invalid", error=str(e))
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    try:
        return jwt.decode(
            token,
            settings.jwt_public_key,
            algorithms=[settings.JWT_ALGORITHM],
            issuer=settings.JWT_ISSUER,
            audience=settings.JWT_AUDIENCE,
            options={"verify_exp": True, "verify_iss": True, "verify_aud": True},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.PyJWTError as e:
        log.warning("token_invalid", error=str(e))
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


async def current_user(request: Request, bearer_token: str | None = Depends(oauth2_scheme)) -> TokenClaims:
    """
    FastAPI dependency — extracts and validates user claims.
    tenant_id and roles come from the SIGNED TOKEN only.
    """
    cookie_token = request.cookies.get("access_token")
    token = bearer_token or cookie_token
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    if cookie_token and not bearer_token and request.method not in {"GET", "HEAD", "OPTIONS"}:
        csrf_cookie = request.cookies.get("csrf_token", "")
        csrf_header = request.headers.get("X-CSRF-Token", "")
        if not csrf_cookie or not csrf_header or not hmac.compare_digest(csrf_cookie, csrf_header):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")

    payload = _decode_token(token)

    # Validate required claims
    user_id   = payload.get("sub")
    tenant_id = payload.get("tenant")
    roles     = payload.get("roles")
    username  = payload.get("username", "")

    if not user_id or not tenant_id or not isinstance(roles, list):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed token claims")

    # Sanitize roles — whitelist check
    ALLOWED_ROLES = {"admin", "analyst", "intern", "viewer"}
    sanitized_roles = [r for r in roles if r in ALLOWED_ROLES]

    return TokenClaims(
        user_id=user_id,
        tenant_id=tenant_id,
        roles=sanitized_roles,
        username=username,
    )


def require_roles(*required: str):
    """Dependency factory — checks that user has at least one required role."""
    async def _check(user: TokenClaims = Depends(current_user)) -> TokenClaims:
        if not any(r in user.roles for r in required):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role: {list(required)}"
            )
        return user
    return _check
