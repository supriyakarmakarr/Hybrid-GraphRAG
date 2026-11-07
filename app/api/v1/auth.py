"""Development demo login and production login for pre-provisioned users."""
import secrets
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from app.core.config import settings
from app.core.db import get_postgres
from app.core.rate_limit import limiter
from app.security.auth import TokenClaims, create_access_token, current_user
from app.security.passwords import verify_password

log = structlog.get_logger()
router = APIRouter(prefix="/auth", tags=["Auth"])

_DEV_USERS = {
    "admin": {"password": "adminpass", "user_id": "dev-admin-001", "tenant_id": "tenant-dev", "roles": ["admin", "analyst"]},
    "intern": {"password": "internpass", "user_id": "dev-intern-001", "tenant_id": "tenant-dev", "roles": ["intern"]},
}


class TokenResponse(BaseModel):
    authenticated: bool = True
    access_token: str | None = None
    token_type: str = "bearer"


def _set_session_cookies(response: Response, token: str):
    secure = settings.ENVIRONMENT == "production"
    response.set_cookie(
        "access_token", token, httponly=True, secure=secure, samesite="lax",
        max_age=settings.JWT_EXPIRY_MINUTES * 60, path="/api",
    )
    response.set_cookie(
        "csrf_token", secrets.token_urlsafe(32), httponly=False, secure=secure,
        samesite="lax", max_age=settings.JWT_EXPIRY_MINUTES * 60, path="/",
    )


@router.get("/csrf")
async def csrf_token(response: Response):
    """Issue the readable CSRF token paired with the HttpOnly access cookie."""
    secure = settings.ENVIRONMENT == "production"
    value = secrets.token_urlsafe(32)
    response.set_cookie("csrf_token", value, httponly=False, secure=secure, samesite="lax", path="/")
    return {"csrf_token": value}


@router.post("/token", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(request: Request, response: Response, form: OAuth2PasswordRequestForm = Depends()):
    """Authenticate demo credentials in development or a provisioned DB user in production."""
    claims = None
    if settings.ENVIRONMENT == "development":
        user = _DEV_USERS.get(form.username)
        if user and secrets.compare_digest(user["password"], form.password):
            claims = user
    else:
        pool = get_postgres()
        async with pool.connection() as conn:
            cursor = await conn.execute(
                """SELECT user_id, tenant_id, username, roles, password_hash
                   FROM users WHERE username=%s AND is_active=TRUE""",
                (form.username,),
            )
            user = await cursor.fetchone()
        if user and verify_password(form.password, user.get("password_hash")):
            claims = user

    if not claims:
        log.warning("login_failed")
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    token = create_access_token(
        user_id=claims["user_id"], tenant_id=claims["tenant_id"],
        roles=list(claims["roles"]), username=claims["username"],
    )
    _set_session_cookies(response, token)
    log.info("login_success", username=claims["username"], tenant=claims["tenant_id"])
    # Preserve the token response for local seed scripts only. Production uses HttpOnly cookies.
    return TokenResponse(access_token=token if settings.ENVIRONMENT == "development" else None)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(response: Response, user: TokenClaims = Depends(current_user)):
    token = create_access_token(user.user_id, user.tenant_id, user.roles, user.username)
    _set_session_cookies(response, token)
    return TokenResponse(access_token=None if settings.ENVIRONMENT == "production" else token)


@router.post("/logout")
async def logout(response: Response, _user: TokenClaims = Depends(current_user)):
    response.delete_cookie("access_token", path="/api", secure=settings.ENVIRONMENT == "production", httponly=True, samesite="lax")
    response.delete_cookie("csrf_token", path="/", secure=settings.ENVIRONMENT == "production", samesite="lax")
    return {"logged_out": True}


@router.get("/me", response_model=TokenClaims)
async def me(user: TokenClaims = Depends(current_user)):
    return user
